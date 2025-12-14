# Agent Instructions

Welcome! Please follow these guidelines when working in this repository:

1. **Design Alignment**
   - Review `DESIGN.md` before implementing new features. Keep architecture and module structure aligned with the documented plan.
   - If you significantly change the approach, update `DESIGN.md` alongside the code.
   - The Node renderer now owns calendar fetching and HTML rendering; Python only retrieves the rendered image for the e-ink driver. Keep changes consistent with this split.

2. **Code Quality**
   - Write clear, well-structured Python following `black` formatting and `ruff` linting conventions.
   - Prefer type hints and dataclasses where appropriate.
   - Include unit tests for new logic and update/extend existing tests when behavior changes.

3. **Testing Expectations**
   - Run the full test suite (e.g., `pytest`) before submitting changes.
   - When adding linting or formatting tools, provide reproducible commands (Makefile or scripts).

4. **Documentation**
   - Update README and docstrings when introducing new modules or changing behavior.
   - Record important architectural decisions in `DESIGN.md`.

5. **Hardware Considerations**
   - Provide mock-friendly code paths so CI can run without the physical e-ink display.
   - Guard hardware-specific imports to prevent failures in environments without the device.

Thanks, and happy hacking!
