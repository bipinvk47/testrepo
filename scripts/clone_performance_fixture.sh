#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-https://github.com/django/django.git}"
REF="${2:-5.1.11}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$ROOT/fixtures/benchmark-subject"
TARGET="$PARENT/django"
mkdir -p "$PARENT"
if [[ -d "$TARGET/.git" ]]; then
  echo "Already exists: $TARGET"
  echo "Remove it to reclone, or: git -C \"$TARGET\" fetch --depth 1 origin tag $REF"
  exit 0
fi
echo "Shallow cloning $REPO (ref=$REF) into $TARGET ..."
git clone --depth 1 --branch "$REF" "$REPO" "$TARGET"
echo "Done. Use: python scripts/whitebox_metrics.py --root \"$ROOT\" --with-benchmark-fixture -o metrics/whitebox_report.json"
