# Iteration log

Short running notes on what broke, what I tried, and which fix worked -
raw material for the reflection in `README.md`.

## Phase 0 - environment & repo setup

- Created a project-local virtualenv at `.venv` (Python 3.12.7 via pyenv).
- `brew install quarto` (cask) needs `sudo` for the pkg installer - had to run it
  manually in a real terminal because the password prompt needs a TTY.
- Decided the optional AI narrative, if built, will use Google Gemini's free
  API tier (no credit card). Core assignment stays LLM-free.

## Phase 1 - Nominatim geocoding

- `osm.py`: one `requests_cache` SQLite session shared by all OSM calls, with an
  identifying User-Agent (Nominatim rejects requests without one).
- Throttle only sleeps for calls that are *not* already cached, checked via
  `session.cache.contains(request=...)`. Observed: 1st call 0.17s, 2nd distinct
  call 1.75s (throttle), repeat of 1st 0.01s (cache hit).
- "Turfmarkt 99, Den Haag" resolves to the Wijnhaven university building - a
  good example of Nominatim picking one specific match; we show `display_name`
  so the user can see which address was used.

## Phase 2 - Overpass + distance

- First attempt failed: HTTP read timeout (20s) was *shorter* than the Overpass
  QL `[timeout:25]`, so we always gave up before the server could answer. Fix:
  separate timeouts - Nominatim 20s, Overpass `(10, 90)` (connect, read), which
  must exceed the QL timeout.
- Overpass load varies a lot: same restaurant query took 81s once, ~10s another
  time; hotels 0.75s. The cache makes repeats ~0.8s (large payload to
  deserialise). A cold query on a busy Overpass is genuinely slow - worth
  discussing (retry/queue behaviour, or a lighter query).
- `out center tags` so ways/relations get a centroid; unnamed elements skipped
  from both list and count. Den Haag centre (Turfmarkt): 280 restaurants /
  90 cafes / 29 hotels within 1 km.
- Server-side timeout remarks are deleted from the cache so they don't linger.

## Phase 3 - Flask UI

- `run_analysis()` in `analysis.py` is the single orchestration point (geocode ->
  find_venues -> sort -> top 5) and returns a plain dict; both the UI and the
  phase-4 report consume that same dict, so their numbers can't drift apart.
- Routes: `GET /`, `POST /analyze`, `POST /report` (stub until phase 4).
  Errors from the `osm` module are caught and shown as a banner with a sensible
  HTTP status (404 address not found, 502 upstream failure).
- Verified via Flask's test client: Den Haag/cafe = 5 sorted rows; Rolde =
  exactly 5 (no banner); Anloo/restaurant = 2 with "n = 2" banner; Diever/hotel
  = 0 with "no venues" message; nonsense address = 404 banner; no category = 400.
- Finding thin test locations is fiddly: many small-village addresses don't
  geocode with a made-up house number. Working sparse cases: "Brink 1, Anloo"
  + restaurant (2), "Brink 1, Diever" + hotel (0).

## Phase 4 - Quarto report + rule-based assessment

- `assess()` in `analysis.py` is a plain if/elif on the count (0-1 / 2-4 / 5+)
  plus a `< 250 m` proximity note - exactly the assignment's thresholds. It
  returns a short paragraph that quotes the actual numbers, so nothing in the
  text is un-sourced. `run_analysis()` stores it as a dict.
- `report.py` builds the whole report as a Markdown string in Python, writes
  `report/_generated.qmd` (no code chunks), and runs
  `quarto render --to typst`. Typst is bundled with Quarto, so no LaTeX.
- Bug found: with `--output name.pdf`, Quarto ignores the project
  `output-dir` and writes the PDF next to the source. Fix: dropped the
  `project:` block from `_quarto.yml` and move the file into `output/` from
  Python (`Path.replace`).
- Changed distance formatting from "nearest 10 m" to whole metres - three
  rows all showing "70 m" looked like a bug.
- Verified: standalone `python report.py` from the fixture, and end-to-end
  `POST /report` returns `application/pdf`. Levels checked: 0 -> lower,
  2 -> moderate, 5 -> higher, all with the right proximity note.

## Phase 5 - README + final test
