"""Flask wiring for the HORECA Competition Lens.

Routes:
    GET  /          - the search form
    POST /analyze   - run an analysis and show the results
    POST /report    - generate a PDF report (wired in phase 4)
"""

from __future__ import annotations

from flask import Flask, render_template, request

from analysis import meters, run_analysis
from osm import CATEGORY_LABELS, AddressNotFound, GeocodingError, OverpassError

app = Flask(__name__)
app.jinja_env.filters["meters"] = meters


@app.get("/")
def index():
    return render_template("index.html", categories=CATEGORY_LABELS)


@app.post("/analyze")
def analyze():
    address = request.form.get("address", "").strip()
    category = request.form.get("category", "")

    if not address:
        return _form_error("Please enter an address.", address, category, 400)
    if category not in CATEGORY_LABELS:
        return _form_error("Please choose a category.", address, category, 400)

    try:
        analysis = run_analysis(address, category)
    except AddressNotFound as exc:
        return _form_error(str(exc), address, category, 404)
    except (GeocodingError, OverpassError) as exc:
        return _form_error(
            f"Could not complete the search: {exc}", address, category, 502
        )

    return render_template("results.html", a=analysis)


@app.post("/report")
def report():
    # Wired in phase 4. For now, re-run the analysis and show the results again
    # so the button does something sensible.
    address = request.form.get("address", "").strip()
    category = request.form.get("category", "")
    try:
        analysis = run_analysis(address, category)
    except (AddressNotFound, GeocodingError, OverpassError) as exc:
        return _form_error(str(exc), address, category, 502)
    return render_template(
        "results.html", a=analysis, notice="PDF report generation arrives in phase 4."
    )


def _form_error(message: str, address: str, category: str, status: int):
    return (
        render_template(
            "index.html",
            categories=CATEGORY_LABELS,
            error=message,
            address=address,
            category=category,
        ),
        status,
    )
