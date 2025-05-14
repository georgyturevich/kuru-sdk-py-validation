# Kuru SDK Integration Tests

## Setup

### For local development:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e /path/to/kuru-sdk-py  # Point to your local SDK copy
```

For regular installation:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-kuru-sdk.txt
```

## Running Tests
```bash
pytest tests/
```

## Linting

This project uses several linting tools to maintain code quality:

- **Black**: Code formatter
- **isort**: Import organizer
- **flake8**: PEP 8 style guide enforcer
- **pylint**: Python code analyzer
- **mypy**: Static type checker

### Running linters

#### Using Make

The project includes Makefile commands to simplify linting tasks:

```bash
# Run all linters in check mode (show what would be changed without applying)
make lint-check

# Run all linters and apply formatting changes
make lint-apply

# Run only Black formatter in check mode
make lint-black-check

# Run only Black formatter and apply changes
make lint-black-apply

# Run only isort formatter in check mode
make lint-isort-check

# Run only isort formatter and apply changes
make lint-isort-apply
```

#### Using the lint script directly

You can also run the linting script directly:

```bash
# Default: Check what would be changed without applying formatting (dry run)
./scripts/lint.sh

# Apply formatting and check all linters
./scripts/lint.sh --apply
# or
./scripts/lint.sh -a

# Run only Black formatter
./scripts/lint.sh --only-black

# Run only Black formatter and apply changes
./scripts/lint.sh --only-black -a

# Run only isort formatter
./scripts/lint.sh --only-isort

# Run only isort formatter and apply changes
./scripts/lint.sh --only-isort -a
```

#### Running individual tools

You can also run each tool separately:

```bash
# Check what would be formatted without applying changes
black --check --diff .
isort --profile black --check-only --diff .

# Format code (apply changes)
black .
isort --profile black .

# Check style
flake8 lib tests
pylint lib tests

# Type checking
mypy lib tests
```
