# Reorder-decision tool (Agent 2) for Frostbite Beverage Co., BULM721 Homework 9.
# It never holds a forecast or inventory number itself: every run reads them from the saved text files.
# Usage: "python3 reorder_tool.py" for one round, "python3 reorder_tool.py batch" for all rounds,
# and "python3 reorder_tool.py charts" for the Problem 2 and weekly-demand charts.

# re lets us pull labeled numbers out of plain-English lines in the rounds file.
import re
# sys gives us the command-line word (batch or charts) and a clean way to stop on errors.
import sys
# Path builds file locations relative to this script, so the tool works from any folder.
from pathlib import Path

# The folder this script lives in, which is also where Agent 1 saves its output.
FOLDER = Path(__file__).parent
# The single-round handoff file that Agent 1 (the demand-sensing agent) writes.
SHARED_FILE = FOLDER / "shared_data.txt"
# The multi-round file that drives the batch run and the webpage.
ROUNDS_FILE = FOLDER / "rounds_summary_data.txt"
# Average weeks in a month, used to turn a monthly forecast into weekly demand.
WEEKS_PER_MONTH = 4.33
# Supplier lead time in weeks: stock must last at least this long while an order is in transit.
LEAD_TIME_WEEKS = 3
# Safety buffer in weeks: extra cover for demand or delivery surprises.
SAFETY_BUFFER_WEEKS = 1
# Reorder threshold: reorder when weeks of supply falls below lead time plus buffer (4 weeks).
THRESHOLD_WEEKS = LEAD_TIME_WEEKS + SAFETY_BUFFER_WEEKS
# Restock target in weeks: a reorder brings inventory back up to this much cover.
TARGET_WEEKS = 8


def read_shared_data():
    """Read the labeled lines in shared_data.txt into a dictionary of numbers."""
    # Fail with a readable message if Agent 1 has not saved its output yet.
    if not SHARED_FILE.exists():
        sys.exit(f"Cannot find {SHARED_FILE.name}. Agent 1 has not saved a forecast yet, so there is nothing to decide on.")
    # Start with an empty set of labeled values.
    values = {}
    # Walk the file one line at a time.
    for line in SHARED_FILE.read_text(encoding="utf-8").splitlines():
        # Only lines shaped like "label: value" carry data; skip blanks and notes.
        if ":" in line:
            # Split at the first colon into the label and its value.
            label, value = line.split(":", 1)
            # Store the value as a number, forgiving stray spaces and thousands commas.
            values[label.strip().lower()] = float(value.strip().replace(",", ""))
    # Check that both required inputs were actually present in the file.
    for needed in ("forecast", "inventory"):
        # A missing label means the handoff is incomplete, so stop instead of guessing.
        if needed not in values:
            sys.exit(f"{SHARED_FILE.name} has no '{needed}:' line. Add it and run the tool again.")
    # Hand the two numbers back to the caller.
    return values


def read_rounds():
    """Read every round from rounds_summary_data.txt as a list of dictionaries."""
    # Fail clearly if the rounds file is missing.
    if not ROUNDS_FILE.exists():
        sys.exit(f"Cannot find {ROUNDS_FILE.name}, so there are no rounds to process.")
    # Pattern for a line such as "Round D - forecast 1500, inventory 400, period February."
    pattern = re.compile(r"Round\s+(\w+).*?forecast\s+([\d,]+).*?inventory\s+([\d,]+).*?period\s+(\w+)", re.I)
    # Collect one entry per round found.
    rounds = []
    # Walk the file one line at a time.
    for line in ROUNDS_FILE.read_text(encoding="utf-8").splitlines():
        # Try to find the round name, forecast, inventory, and period on this line.
        match = pattern.search(line)
        # Lines that do not match (blank lines, notes) are skipped.
        if match:
            # Unpack the four captured pieces of the line.
            name, forecast, inventory, period = match.groups()
            # Save the round, converting the two numbers from text and dropping any commas.
            rounds.append({"round": f"Round {name.upper()}", "period": period,
                           "forecast": float(forecast.replace(",", "")), "inventory": float(inventory.replace(",", ""))})
    # Hand the full list back to the caller.
    return rounds


def decide(forecast, inventory):
    """Apply the Chapter 6 weeks-of-supply logic and return the reorder decision."""
    # Convert the monthly forecast into expected units per week.
    weekly_demand = forecast / WEEKS_PER_MONTH
    # Weeks of supply: how long current stock lasts at that weekly rate.
    weeks_of_supply = inventory / weekly_demand
    # Reorder only when cover has dropped below the 4-week threshold.
    reorder = weeks_of_supply < THRESHOLD_WEEKS
    # Order enough to get back to 8 weeks of cover, or nothing when holding.
    order_quantity = round(TARGET_WEEKS * weekly_demand - inventory) if reorder else 0
    # Return everything the report and the webpage need.
    return {"weekly_demand": weekly_demand, "weeks_of_supply": weeks_of_supply,
            "decision": "REORDER NOW" if reorder else "HOLD", "order_quantity": order_quantity}


def bar_chart(title, labels, values, threshold=None, decimals=2):
    """Draw a simple bar chart as SVG text, with an optional dashed threshold line."""
    # Scale the chart to the tallest thing shown, so every bar and the line fit.
    top = max(values + [threshold or 0, 1]) * 1.2
    # Open the drawing and add the chart title.
    svg = f'<svg viewBox="0 0 520 300" width="520" role="img" aria-label="{title}"><text x="260" y="20" text-anchor="middle" font-weight="bold">{title}</text>'
    # Each bar gets an equal share of the 440-unit plotting width.
    slot = 440 / len(values)
    # Draw one bar per value.
    for i, (label, value) in enumerate(zip(labels, values)):
        # Bar height in drawing units, out of a 220-unit plotting height.
        height = value / top * 220
        # Left edge of this bar, centered inside its slot.
        x = 50 + i * slot + slot * 0.2
        # Bars under the threshold are red (reorder territory); the rest are blue.
        color = "#c0392b" if threshold and value < threshold else "#2e6da4"
        # The bar itself.
        svg += f'<rect x="{x:.1f}" y="{260 - height:.1f}" width="{slot * 0.6:.1f}" height="{height:.1f}" fill="{color}"/>'
        # The value printed just above the bar.
        svg += f'<text x="{x + slot * 0.3:.1f}" y="{254 - height:.1f}" text-anchor="middle" font-size="12">{value:,.{decimals}f}</text>'
        # The category label under the bar.
        svg += f'<text x="{x + slot * 0.3:.1f}" y="278" text-anchor="middle" font-size="12">{label}</text>'
    # Draw the threshold line only when one was requested.
    if threshold:
        # Vertical position of the threshold on the same scale as the bars.
        y = 260 - threshold / top * 220
        # The dashed line and its label.
        svg += f'<line x1="50" x2="490" y1="{y:.1f}" y2="{y:.1f}" stroke="#333" stroke-dasharray="6 4"/><text x="490" y="{y - 5:.1f}" text-anchor="end" font-size="12">{threshold}-week threshold</text>'
    # Add the baseline and close the drawing.
    return svg + '<line x1="50" x2="490" y1="260" y2="260" stroke="#333"/></svg>'


def line_chart(title, labels, values):
    """Draw a simple line chart as SVG text."""
    # Scale to the largest value with some headroom.
    top = max(values) * 1.2
    # Horizontal gap between points across the 440-unit plotting width.
    step = 440 / max(len(values) - 1, 1)
    # Work out the x and y position of every point.
    points = [(50 + i * step, 260 - v / top * 220) for i, v in enumerate(values)]
    # Open the drawing, add the title, and connect the points with one line.
    svg = f'<svg viewBox="0 0 540 300" width="540" role="img" aria-label="{title}"><text x="270" y="20" text-anchor="middle" font-weight="bold">{title}</text><polyline fill="none" stroke="#2e6da4" stroke-width="3" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in points)}"/>'
    # Mark and label each point.
    for (x, y), label, value in zip(points, labels, values):
        # The dot, its value above it, and its round label on the axis.
        svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2e6da4"/><text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-size="12">{value:.1f}</text><text x="{x:.1f}" y="278" text-anchor="middle" font-size="12">{label}</text>'
    # Add the baseline and close the drawing.
    return svg + '<line x1="40" x2="500" y1="260" y2="260" stroke="#333"/></svg>'


def page(title, body):
    """Wrap chart and table content in a minimal, clean webpage."""
    # One shared look for every page the tool writes.
    style = "body{font-family:Arial,sans-serif;max-width:1100px;margin:30px auto;padding:0 16px;color:#222}table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:8px;text-align:right}th{background:#1f3a5f;color:#fff}td:nth-child(-n+2),td:nth-child(7){text-align:left}.reorder{background:#f9d6d2}.hold{background:#d9efd9}.charts{display:flex;flex-wrap:wrap;gap:20px;margin-top:24px}"
    # Return the complete HTML document as text.
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{style}</style></head><body><h1>{title}</h1>{body}</body></html>'


def run_single():
    """Round-by-round mode: decide on whatever is currently saved in shared_data.txt."""
    # Read the forecast and inventory fresh from the file on every run.
    data = read_shared_data()
    # Apply the reorder logic to those two numbers.
    result = decide(data["forecast"], data["inventory"])
    # Show which file the inputs came from, as evidence of the handoff.
    print(f"Read from {SHARED_FILE.name}: forecast = {data['forecast']:,.0f} units, inventory = {data['inventory']:,.0f} units")
    # Show the weekly demand the forecast implies.
    print(f"Weekly demand:   {result['weekly_demand']:.1f} units/week")
    # Show weeks of supply next to the threshold it is compared against.
    print(f"Weeks of supply: {result['weeks_of_supply']:.2f} weeks (threshold {THRESHOLD_WEEKS} weeks)")
    # Show the decision, with the order quantity only when there is one.
    print(f"Decision:        {result['decision']}" + (f", order {result['order_quantity']:,} units" if result["order_quantity"] else ""))


def run_batch():
    """Batch mode: process every saved round in one run and rebuild the webpage."""
    # Read all rounds, then attach the decision results to each one.
    rounds = [{**r, **decide(r["forecast"], r["inventory"])} for r in read_rounds()]
    # Print a header row for the on-screen summary.
    print(f"{'Round':<9}{'Period':<10}{'Forecast':>9}{'Inventory':>10}{'Wkly demand':>12}{'Wks supply':>11}  {'Decision':<12}{'Order qty':>9}")
    # Start the webpage table with matching headers.
    rows = "<table><tr><th>Round</th><th>Period</th><th>Forecast (units)</th><th>Inventory (units)</th><th>Weekly demand</th><th>Weeks of supply</th><th>Decision</th><th>Order quantity</th></tr>"
    # Add one line to the screen summary and one row to the webpage per round.
    for r in rounds:
        # The on-screen summary line for this round.
        print(f"{r['round']:<9}{r['period']:<10}{r['forecast']:>9,.0f}{r['inventory']:>10,.0f}{r['weekly_demand']:>12.1f}{r['weeks_of_supply']:>11.2f}  {r['decision']:<12}{r['order_quantity']:>9,}")
        # The matching webpage row, colored red for REORDER NOW and green for HOLD.
        rows += f"<tr class=\"{'reorder' if r['order_quantity'] else 'hold'}\"><td>{r['round']}</td><td>{r['period']}</td><td>{r['forecast']:,.0f}</td><td>{r['inventory']:,.0f}</td><td>{r['weekly_demand']:.1f}</td><td>{r['weeks_of_supply']:.2f}</td><td>{r['decision']}</td><td>{r['order_quantity']:,}</td></tr>"
    # Short labels (A, B, C...) keep the chart axes readable.
    labels = [r["round"].replace("Round ", "") for r in rounds]
    # Build the two charts the homework asks for.
    charts = bar_chart("Weeks of supply by round", labels, [r["weeks_of_supply"] for r in rounds], THRESHOLD_WEEKS) + bar_chart("Order quantity by round (units)", labels, [r["order_quantity"] for r in rounds], decimals=0)
    # Assemble the full page: an explanation line, the table, then the charts.
    html = page("Frostbite Beverage Co. Reorder Decisions", f"<p>Reorder when weeks of supply is below {THRESHOLD_WEEKS} weeks ({LEAD_TIME_WEEKS}-week lead time plus {SAFETY_BUFFER_WEEKS}-week safety buffer). Orders restock to {TARGET_WEEKS} weeks of supply.</p>{rows}</table><div class=\"charts\">{charts}</div>")
    # Save the page twice: under its homework name and as index.html for GitHub Pages.
    for name in ("batch_summary.html", "index.html"):
        # Write the same content to each file.
        (FOLDER / name).write_text(html, encoding="utf-8")
    # Confirm how many rounds were processed and which files were refreshed.
    print(f"\nProcessed {len(rounds)} rounds. Updated batch_summary.html and index.html.")


def run_charts(before, after):
    """Build charts.html: the Problem 2 before/after chart and the weekly-demand line chart."""
    # Use the inventory currently saved in shared_data.txt for the before/after comparison.
    inventory = read_shared_data()["inventory"]
    # Weeks of supply for the original forecast and for the edited forecast.
    supply = [decide(f, inventory)["weeks_of_supply"] for f in (before, after)]
    # The Problem 2 chart: two bars against the 4-week threshold.
    body = bar_chart("Weeks of supply before and after the edit", [f"Forecast {before:,.0f}", f"Forecast {after:,.0f}"], supply, THRESHOLD_WEEKS)
    # The first three rounds (A, B, C) for the weekly-demand trend.
    first_three = read_rounds()[:3]
    # The line chart of weekly demand across those rounds.
    body += line_chart("Weekly demand, Rounds A to C (units/week)", [f"{r['round']} ({r['period']})" for r in first_three], [decide(r["forecast"], r["inventory"])["weekly_demand"] for r in first_three])
    # Save both charts on one page.
    (FOLDER / "charts.html").write_text(page("Homework 9 Charts", f'<div class="charts">{body}</div>'), encoding="utf-8")
    # Confirm what was written.
    print(f"Saved charts.html (before/after weeks of supply: {supply[0]:.2f} vs {supply[1]:.2f}).")


# Only run when this file is started directly, not when another program imports it.
if __name__ == "__main__":
    # The first word after the script name picks the mode; no word means a single round.
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    # "batch" processes every round in rounds_summary_data.txt.
    if mode == "batch":
        run_batch()
    # "charts 1544 1800" draws the before/after chart for those two forecasts plus the trend line.
    elif mode == "charts":
        run_charts(float(sys.argv[2]) if len(sys.argv) > 2 else 1544, float(sys.argv[3]) if len(sys.argv) > 3 else 1800)
    # Anything else runs the single-round decision from shared_data.txt.
    else:
        run_single()
