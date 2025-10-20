# Repository Guidelines

## Project Structure & Module Organization
Core data flow spans five layers: `layer1/` ingests, infers schemas, and persists clean datasets; `layer2/` and `layer3/` classify, apply audit rules, and prepare exports; `layer4/` coordinates cross-layer orchestration; `layer5/` exposes APIs, external bridges, and cloud connectors. Reusable helpers sit in `utils/`, configuration in `config/`, runtime artifacts in `data/`, and telemetry under `logs/`. Automated checks follow `tests/` with discovery defined in `pytest.ini`.

## Build, Test, and Development Commands
- `install.bat` — creates `dap_env` and installs `requirements.txt`.
- `start_all.bat` — menu-driven launcher for GUI, API, agent, monitor, or full stack (activate `dap_env` first).
- `python dap_launcher.py` — opens the desktop launcher directly.
- `python -m pytest` — executes the suite; combine markers such as `-m "unit and not slow"` to narrow coverage.

## Coding Style & Naming Conventions
Target Python 3.8+ with four-space indentation and PEP 8 alignment. Use `snake_case` for modules and functions, `PascalCase` for classes, and upper snake for constants; prefix new files with their pipeline layer when practical. Format code with `black .` and lint via `flake8 layer*/ utils/ main_engine.py` before submission. Keep comments outcome-focused and reserve docstrings for public interfaces or non-obvious workflows.

## Testing Guidelines
Place tests beside related functionality inside `tests/` and name them `test_<feature>.py`. Leverage the predefined markers (`unit`, `integration`, `security`, `slow`, etc.) to signal intent and keep suites skimmable. Every change should add at least one deterministic assertion against new logic; store reusable fixtures under `tests/fixtures/` or inline parametrization. When touching ingestion or AI coordination, run `python -m pytest --durations=10` to watch for regressions.

## Commit & Pull Request Guidelines
The current workspace lacks accessible Git history, so default to Conventional Commit prefixes (`feat:`, `fix:`, `refactor:`, `chore:`) with subjects under 72 characters. Pull requests must include a concise summary, linked task or issue, evidence of local testing (command output or rationale), and updated docs for configuration or API changes. Surface risky steps—database migrations, new ports, external dependencies—prominently for reviewers.

## Configuration & Security Notes
Project settings live in `config/settings.py` and audit logic in `config/audit_rules.yaml`; document new keys in-place and supply safe defaults. Keep secrets out of version control and load them from environment variables set during `install.bat` or local profiles. Before shipping ingestion or storage changes, review `logs/dap.log` and `performance_monitor.py` output. External integrations added in `layer5/` should enforce explicit timeouts, retries, and input validation.
