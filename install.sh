#!/bin/sh
# Install or update tokencount. Re-run any time to get the latest version.
#
#   curl -fsSL https://raw.githubusercontent.com/zanellig/tokencount/main/install.sh | sh
#
# Override the destination with BINDIR, the version with REF:
#   curl -fsSL .../install.sh | BINDIR=/usr/local/bin REF=v1.0.0 sh
set -eu

REF="${REF:-main}"
BINDIR="${BINDIR:-$HOME/.local/bin}"
URL="https://raw.githubusercontent.com/zanellig/tokencount/$REF/tokencount.py"
DEST="$BINDIR/tokencount"

command -v python3 >/dev/null || { echo "tokencount needs python3 (3.8+)" >&2; exit 1; }

mkdir -p "$BINDIR"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL "$URL" -o "$tmp"
# Sanity check: refuse to install an error page or a truncated download.
python3 -c 'import sys; compile(open(sys.argv[1]).read(), "tokencount", "exec")' "$tmp" \
  || { echo "downloaded file is not valid Python; aborting" >&2; exit 1; }
chmod 755 "$tmp"
mv "$tmp" "$DEST"
trap - EXIT

echo "installed $DEST ($REF)"
case ":$PATH:" in
  *":$BINDIR:"*) ;;
  *) echo "note: $BINDIR is not on your PATH" >&2 ;;
esac
