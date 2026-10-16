#!/usr/bin/env bash
# One-off: download Swiss Ephemeris data files into backend/ephe/ (output is committed).
set -euo pipefail
BASE="https://github.com/aloistr/swisseph/raw/master/ephe"
DEST="$(cd "$(dirname "$0")/.." && pwd)/ephe"
mkdir -p "$DEST"
for f in sepl_18.se1 semo_18.se1 seas_18.se1; do
  curl -fsSL "$BASE/$f" -o "$DEST/$f"
  [ -s "$DEST/$f" ] || { echo "ERROR: $f is empty" >&2; exit 1; }
  echo "ok $f $(wc -c < "$DEST/$f") bytes"
done
