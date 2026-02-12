#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3 is required but was not found in PATH."
  exit 1
fi

"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install "${ROOT_DIR}"

USER_BASE="$("${PYTHON_BIN}" -m site --user-base 2>/dev/null || true)"
USER_BIN="${USER_BASE}/bin"
USER_CMD="${USER_BIN}/ai-pr-review"
GLOBAL_CMD="/usr/local/bin/ai-pr-review"

if [ -x "${USER_CMD}" ] && [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
  ln -sf "${USER_CMD}" "${GLOBAL_CMD}"
fi

cat <<MSG
Installation complete.

Run the tool from anywhere:
  ai-pr-review --help

If the command is not found, add this directory to PATH:
  ${USER_BIN}
MSG
