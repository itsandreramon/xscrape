#!/bin/bash
# run shellcheck on all shell scripts
set -e

cd "$(dirname "$0")/.."

shellcheck -x -e SC1091 scripts/*.sh docker/*.sh
