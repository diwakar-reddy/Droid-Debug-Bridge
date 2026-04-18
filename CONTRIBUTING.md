# Contributing to ddb

Thanks for your interest in contributing to Droid Debug Bridge!

## Development Setup

```bash
git clone https://github.com/diwakar-reddy/Droid-Debug-Bridge.git
cd Droid-Debug-Bridge
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest                                    # run all tests
pytest --cov=ddb --cov-report=term-missing  # with coverage
```

## Linting & Formatting

```bash
ruff check src/ tests/        # lint
black src/ tests/              # format
black --check src/ tests/     # check formatting
mypy src/ddb                  # type check
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Add tests for any new commands or behavior changes.
3. Make sure all checks pass: `pytest`, `ruff check`, `black --check`.
4. Open a PR against `main` with a clear description of the change.

## Adding a New Command

1. Implement the function in the appropriate module under `src/ddb/modules/`.
2. Add the argparse subparser in `cli.py`.
3. Add the dispatch branch in `_dispatch()`.
4. Add a dispatch test in `tests/test_cli.py`.

## Code Style

- Line length: 100 characters (configured in `pyproject.toml`)
- Formatting: Black
- Linting: Ruff (E, F, W, I rules)
- All commands must return structured JSON with a `success` field.
