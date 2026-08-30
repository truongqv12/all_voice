#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCREENSHOTS_DIR="${1:-$ROOT_DIR/frontend/e2e/__screenshots__/phase7}"
RUBRIC_FILE="$SCRIPT_DIR/rubric.md"
SCHEMA_FILE="$SCRIPT_DIR/findings.schema.json"

if [ ! -d "$SCREENSHOTS_DIR" ]; then
  echo "Error: Screenshots directory $SCREENSHOTS_DIR does not exist." >&2
  exit 1
fi

COUNT=$(find "$SCREENSHOTS_DIR" -type f -name "*.png" | wc -l)
echo "Running vision review on $COUNT screenshots in $SCREENSHOTS_DIR..." >&2

agy --dangerously-skip-permissions \
    --add-dir "$SCREENSHOTS_DIR" \
    -p "$(cat "$RUBRIC_FILE")" \
    --output-format json \
    --json-schema "$SCHEMA_FILE"
