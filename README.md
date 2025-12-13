# eink_display
[![CI](https://github.com/mweiden/eink_display/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

<img width="1600" height="960" alt="tufte_day_sample" src="https://github.com/user-attachments/assets/7500c144-e438-408e-bb2e-a2e123cc38d7" />

Python application for driving a Waveshare 7.5" e-ink display with a daily calendar view rendered from Google Calendar data. The Node renderer now owns calendar fetching and HTML rendering; Python simply downloads the pre-rendered PNG from the Node server's root path and pushes it to the display driver. See [DESIGN.md](DESIGN.md) for the architectural plan.

## Configuration

Both the Node renderer and the Python wrapper read configuration from environment variables or an optional `.env` file in the working directory. At minimum, set the following values before starting the program:

| Variable | Description |
| --- | --- |
| `GOOGLE_CREDENTIALS_PATH` | Absolute path to the Google service account JSON used for Calendar API access. The file must exist when the Node renderer starts. |
| `CALENDAR_IDS` | Comma-separated list of Google Calendar IDs to display (e.g., `primary,team@example.com`). |

Example `.env` file:

```dotenv
GOOGLE_CREDENTIALS_PATH=/home/pi/secrets/service-account.json
CALENDAR_IDS=primary,team@example.com
```

## Development

- Review the contributor guidelines in [AGENTS.md](AGENTS.md) before making changes.
- Create and activate a virtual environment (e.g., `python -m venv .venv && source .venv/bin/activate`).
- Install development dependencies as needed (e.g., `pip install -r requirements-dev.txt` if using a shared requirements file).
- Configure the renderer preview directory (see below) to iterate on layouts without e-ink hardware attached.

### Running the renderer server

The Fastify/Puppeteer service fetches Google Calendar data and renders the calendar at its root path. Start it with your
credentials and calendar IDs, then open `http://localhost:${PORT:-3000}/` in a browser or let the Python code fetch the PNG from
that same URL:

```bash
cd eink_display/rendering/node_renderer
PUPPETEER_SKIP_DOWNLOAD=1 npm install
PORT=3000 CALENDAR_IDS=primary GOOGLE_CREDENTIALS_PATH=/path/to/creds.json npm run dev
```

When credentials are not available, the server falls back to bundled sample events so that previews and tests still render.
Python no longer posts custom event payloads; it simply downloads the rendered PNG from the root path.

### Rendering preview images

We now call the original React renderer directly via a small Fastify/Puppeteer service that ships with the repository
(`eink_display/rendering/node_renderer`). The Python helpers automatically install dependencies on first use, but you can also do
so manually:

```bash
cd eink_display/rendering/node_renderer
PUPPETEER_SKIP_DOWNLOAD=1 npm install
```

Render previews with the provided helper script, which saves whatever the Node server renders at the root path (live calendar data or the built-in sample events) to `previews/tufte_day_sample.png` by default:

```bash
python scripts/render_sample_calendar.py
```

Pass `--output /path/to/file.png` or `--path /debug` to change the target file or server route. The script emits a `480×800` layout rendered at `2×` device scale (`960×1600` PNG) so text remains crisp on the Waveshare panel. This is the same PNG that the integration tests validate.

## Testing

Run the full automated test suite locally before opening a pull request:

```bash
pytest
```

The continuous integration workflow mirrors this command to help ensure consistent results.
