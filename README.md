# eink_display
[![CI](https://github.com/mweiden/eink_display/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

<img width="1600" height="960" alt="tufte_day_sample" src="https://github.com/user-attachments/assets/7500c144-e438-408e-bb2e-a2e123cc38d7" />

Python application for driving a Waveshare 7.5" e-ink display with a daily calendar view rendered from Google Calendar data. See [DESIGN.md](DESIGN.md) for the architectural plan.

## Configuration

The application reads configuration from environment variables or an optional `.env` file in the working directory. At minimum, set the following values before starting the program:

| Variable | Description |
| --- | --- |
| `GOOGLE_CREDENTIALS_PATH` | Absolute path to the Google service account JSON used for Calendar API access. The file must exist when the application starts. |
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

### Rendering preview images

We now call the original React renderer directly via a small Fastify/Puppeteer service that ships with the repository
(`eink_display/rendering/node_renderer`). The Python helpers automatically install dependencies on first use, but you can also do
so manually:

```bash
cd eink_display/rendering/node_renderer
PUPPETEER_SKIP_DOWNLOAD=1 npm install
```

Render previews with the provided helper script, which writes a sample schedule to `previews/tufte_day_sample.png` by default:

```bash
python scripts/render_sample_calendar.py
```

Pass `--date YYYY-MM-DD` or `--output /path/to/file.png` to customise the rendered day or output path. The script emits a `480×800` layout rendered at `2×` device scale (`960×1600` PNG) so text remains crisp on the Waveshare panel. This is the same PNG that the integration tests validate.

## Testing

Run the full automated test suite locally before opening a pull request:

```bash
pytest
```

The continuous integration workflow mirrors this command to help ensure consistent results.
