# eink_display
[![CI](https://github.com/mweiden/eink_display/actions/workflows/ci.yml/badge.svg)](https://github.com/<OWNER>/<REPO>/actions/workflows/ci.yml)

Python application for driving a Waveshare 7.5" e-ink display with a daily calendar view rendered from Google Calendar data. See [DESIGN.md](DESIGN.md) for the architectural plan.

## Development

- Review the contributor guidelines in [AGENTS.md](AGENTS.md) before making changes.
- Create and activate a virtual environment (e.g., `python -m venv .venv && source .venv/bin/activate`).
- Install development dependencies as needed (e.g., `pip install -r requirements-dev.txt` if using a shared requirements file).

## Testing

Run the full automated test suite locally before opening a pull request:

```bash
pytest
```

The continuous integration workflow mirrors this command to help ensure consistent results.
