#!/bin/sh

set -eu

PKG="brother_printer_fwupd"
echo "--> Running isort"
uv run isort "${PKG}"
# echo "--> Running black"
# uv run black "${PKG}"
echo "--> Running pylint"
uv run pylint --exit-zero --jobs 0 "${PKG}"
echo "--> Running pyre"
set +e  # pyre has no flag to exit with 0
uv run pyre check
set -e
echo "--> Running ruff"
uv run ruff check
uv run ruff format
echo "--> Running mypy"
set +e  # mypy has no flag to exit with 0
uv run mypy "${PKG}"
set -e
# echo "--> Running tox"
# uv run tox
