"""Flask wiring for the HORECA Competition Lens.

Routes:
    GET  /          - the search form
    POST /analyze   - run an analysis and show the results
    POST /report    - generate a PDF report (wired in phase 4)
"""

from __future__ import annotations

import subprocess

from flask import Flask, render_template, request, send_file

from analysis import meters, run_analysis
from osm import CATEGORY_LABELS, AddressNotFound, GeocodingError, OverpassError
from report import generate_report

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
    address = request.form.get("address", "").strip()
    category = request.form.get("category", "")
    if not address or category not in CATEGORY_LABELS:
        return _form_error("Please run a search first.", address, category, 400)

    try:
        analysis = run_analysis(address, category)
        pdf_path = generate_report(analysis)
    except (AddressNotFound, GeocodingError, OverpassError) as exc:
        return _form_error(str(exc), address, category, 502)
    except FileNotFoundError:
        return _form_error(
            "Quarto is not installed or not on PATH - run 'brew install quarto'.",
            address, category, 500,
        )
    except subprocess.CalledProcessError as exc:
        app.logger.error("quarto render failed:\n%s", exc.stderr)
        return _form_error(
            "Report rendering failed. Check the server log for Quarto output.",
            address, category, 500,
        )

    return send_file(pdf_path, as_attachment=True, download_name=pdf_path.name)


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
