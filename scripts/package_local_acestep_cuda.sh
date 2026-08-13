#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="${ACESTEP_CPP_DIR:-$PROJECT_DIR/vendor/acestep.cpp}"
OUTPUT_DIR="${1:-$PROJECT_DIR/dist}"
ASSET="acestep.cpp-linux-x86_64-cuda.tar.gz"

if [[ ! -x "$SOURCE_DIR/build/ace-server" ]]; then
  echo "ace-server not found: $SOURCE_DIR/build/ace-server" >&2
  exit 1
fi
if [[ ! -f "$SOURCE_DIR/LICENSE" ]]; then
  echo "Upstream license not found: $SOURCE_DIR/LICENSE" >&2
  exit 1
fi

revision="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
staging="$(mktemp -d)"
trap 'rm -rf -- "$staging"' EXIT
mkdir -p "$staging/package/build" "$OUTPUT_DIR"

find "$SOURCE_DIR/build" -maxdepth 1 \
  \( -type f -o -type l \) \
  \( -executable -o -name '*.so' -o -name '*.so.*' \) \
  -exec cp -a -- {} "$staging/package/build/" \;
cp -- "$SOURCE_DIR/LICENSE" "$staging/package/LICENSE.acestep.cpp"
printf 'Source: https://github.com/ServeurpersoCom/acestep.cpp\nRevision: %s\n' \
  "$revision" > "$staging/package/SOURCE.txt"

tar -C "$staging/package" -czf "$OUTPUT_DIR/$ASSET" .
sha256sum "$OUTPUT_DIR/$ASSET" > "$OUTPUT_DIR/$ASSET.sha256"
echo "Created $OUTPUT_DIR/$ASSET"
