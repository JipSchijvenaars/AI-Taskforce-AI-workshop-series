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

## Phase 4 - Quarto report + rule-based assessment

## Phase 5 - README + final test
