#!/usr/bin/env bash

set -e

IGNORES="
"

poetry run safety check $IGNORES --full-report | tee reports/safety.ansi

exit "${PIPESTATUS[0]}"
