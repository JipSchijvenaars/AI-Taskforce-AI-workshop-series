"""Turn an analysis dict into a PDF report with Quarto.

The whole report is built as Markdown text here in Python, written to a
temporary `.qmd` file, and Quarto converts it Markdown -> Typst -> PDF. No
code runs inside the `.qmd`, so no extra Quarto/Jupyter dependencies are
needed. Typst is bundled with Quarto, so no LaTeX either.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from analysis import meters

_ROOT = Path(__file__).resolve().parent
REPORT_DIR = _ROOT / "report"
OUTPUT_DIR = _ROOT / "output"
QMD_PATH = REPORT_DIR / "_generated.qmd"  # overwritten on every run

LIMITATIONS = (
    "OpenStreetMap data can be incomplete or out of date. Category matching is "
    "deliberately strict (amenity=cafe / amenity=restaurant / tourism=hotel), so "
    "venues tagged differently (bar, pub, fast_food, guest_house, hostel, ...) are "
    "not counted. Venues without a name are excluded. Nominatim returns a single "
    "best-guess location for the entered address. Treat this report as an "
    "exploratory indication, not a market survey - validate on the ground before "
    "making a real business decision."
)


def _table(matches: list[dict]) -> str:
    if not matches:
        return "_No matching venues were found within 1 km._"
    lines = [
        "| # | Name | Type | Website | Distance |",
        "|---|------|------|---------|----------|",
    ]
    for i, m in enumerate(matches, start=1):
        lines.append(
            f"| {i} | {m['name']} | {m['kind']} | {m['website'] or '-'} "
            f"| {meters(m['distance_m'])} |"
        )
    return "\n".join(lines)


def build_markdown(a: dict) -> str:
    """Build the full report as a Quarto Markdown string."""
    cat = a["category_label"].lower()
    assessment = a["assessment"] or {}
    if a["closest_distance_m"] is None:
        nearest = "none found"
    else:
        nearest = f"about {meters(a['closest_distance_m'])}"

    lines = [
        "---",
        'title: "HORECA Competition Lens - location report"',
        "---",
        "",
        f"**Generated:** {a['generated_at']}",
        "",
        "## Search",
        "",
        f"- **Address entered:** {a['address_input']}",
        f"- **Resolved to:** {a['address_resolved']}",
        f"- **Category:** {a['category_label']}",
        f"- **Search radius:** {a['radius_m']} m (1 km)",
        "",
        "## Five closest venues",
        "",
        _table(a["matches"]),
        "",
        "## Findings",
        "",
        f"- **Total mapped {cat} venues within 1 km:** {a['total_within_radius']}",
        f"- **Distance to nearest:** {nearest}",
        "",
        "## Indicative competition assessment",
        "",
        assessment.get("summary", "No assessment available."),
    ]

    if assessment.get("proximity_note"):
        lines += ["", f"> {assessment['proximity_note']}"]

    if a.get("ai_narrative"):
        lines += [
            "",
            "## AI-assisted narrative",
            "",
            f"*AI-assisted (verify against the data above):* {a['ai_narrative']}",
        ]

    lines += ["", "## Limitations", "", LIMITATIONS, ""]
    return "\n".join(lines)


def generate_report(analysis: dict) -> Path:
    """Render the analysis to a PDF and return its path in `output/`.

    Raises `FileNotFoundError` if Quarto is not installed, or
    `subprocess.CalledProcessError` if the render fails.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    QMD_PATH.write_text(build_markdown(analysis), encoding="utf-8")

    pdf_name = f"report-{datetime.now():%Y%m%d-%H%M%S}.pdf"
    subprocess.run(
        ["quarto", "render", QMD_PATH.name, "--to", "typst", "--output", pdf_name],
        cwd=REPORT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    # Quarto writes --output next to the source; move it into output/.
    produced = REPORT_DIR / pdf_name
    destination = OUTPUT_DIR / pdf_name
    produced.replace(destination)
    return destination


if __name__ == "__main__":
    # Standalone render from the sample fixture: python report.py
    import json

    sample = json.loads((REPORT_DIR / "sample_analysis.json").read_text())
    print("Wrote", generate_report(sample))
