# HORECA Competition Lens

A small local web app that helps an aspiring hospitality entrepreneur get a
first impression of nearby competition before choosing a location for a
**café**, **restaurant** or **hotel**.

Preparation assignment for the AI Taskforce workshop series (The Hague
University of Applied Sciences). The goal is a small, working, explainable
tool - not a production system or a real business recommendation.

## What it does

1. You enter an address and pick one category (café / restaurant / hotel).
2. The address is geocoded with **OpenStreetMap Nominatim**.
3. Matching mapped establishments within **1 km** are fetched from the
   **Overpass API**.
4. The five closest are shown with name, type, website (if known) and
   straight-line distance.
5. A button generates a **Quarto PDF report** with a transparent,
   rule-based indication of local competition.

## Stack

Python + Flask · OpenStreetMap (Nominatim + Overpass) · Quarto (Typst) · runs
locally, no deployment.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install quarto        # macOS; needs Quarto >= 1.4 (bundled Typst)
quarto check               # should report Typst OK
```

## Run

```bash
flask --app app run --debug
# open http://127.0.0.1:5000
```

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Flask routes (`/`, `/analyze`, `/report`) - wiring only |
| `osm.py` | Nominatim geocoding + Overpass venue search + HTTP cache |
| `analysis.py` | distance, orchestration, rule-based assessment |
| `report.py` | build report content -> `quarto render` -> PDF |
| `report/` | `_quarto.yml` + sample data |
| `output/` | generated PDFs (git-ignored) |
| `deliverables/` | the final report that is handed in |

## Limitations

OpenStreetMap data can be incomplete or out of date. Category matching is
deliberately strict (`amenity=cafe` / `amenity=restaurant` / `tourism=hotel`),
so alternatively tagged venues (bar, pub, fast_food, guest_house, ...) are not
counted. Unnamed objects are excluded. Treat the report as an exploratory
indication, not a market survey - validate on the ground before deciding.

## AI-assisted narrative

Not implemented yet. `analysis.py` leaves a hook (`ai_narrative`) for the
optional extension; if added it would use Google Gemini's free tier and be
clearly labelled as AI-assisted in the report.

## Reflection

_To be completed in Phase 5._

- What worked well?
- What did not work at first?
- One issue solved by iterating with the coding harness?
- One thing still unclear / to discuss in the workshop?
