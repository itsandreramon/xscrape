#!/bin/bash
# run linters on shell and python files
set -e

cd "$(dirname "$0")/.."

echo "shellcheck..."
shellcheck -x -e SC1091 scripts/*.sh docker/*.sh

echo "ruff..."
ruff check xscrape/
