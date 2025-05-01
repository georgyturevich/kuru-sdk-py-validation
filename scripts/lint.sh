#!/bin/bash
set -e

# Default settings
APPLY_CHANGES=""
ONLY_BLACK=""
ONLY_ISORT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --apply|-a)
      APPLY_CHANGES="true"
      shift
      ;;
    --only-black)
      ONLY_BLACK="true"
      shift
      ;;
    --only-isort)
      ONLY_ISORT="true"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ -n "$APPLY_CHANGES" ]; then
  echo "Running in apply mode (will apply formatting changes)"
else
  echo "Running in dry-run mode (will show changes but not apply them)"
fi

# Run isort if not only-black or it's only-isort
if [ -z "$ONLY_BLACK" ] || [ -n "$ONLY_ISORT" ]; then
  echo "Running isort..."
  if [ -n "$APPLY_CHANGES" ]; then
    isort --profile black .
  else
    isort --profile black --check-only --diff .
  fi
fi

# Run black if not only-isort or it's only-black
if [ -z "$ONLY_ISORT" ] || [ -n "$ONLY_BLACK" ]; then
  echo "Running black..."
  if [ -n "$APPLY_CHANGES" ]; then
    black .
  else
    black --check --diff .
  fi
fi

# Run remaining linters only if not running specific formatters
if [ -z "$ONLY_BLACK" ] && [ -z "$ONLY_ISORT" ]; then
  echo "Running flake8..."
  flake8 lib tests

  echo "Running pylint..."
  pylint lib tests

  echo "Running mypy..."
  mypy lib tests
fi

echo "All linting checks passed!"