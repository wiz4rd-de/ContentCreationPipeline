#!/usr/bin/env bash
# macOS launcher for the SEO Content Pipeline.
# Double-click from Finder or run `./run.command` from Terminal.
#
# Flow:
#   1. cd to this script's directory (so api.env + uv + venv all resolve locally).
#   2. Clear the Gatekeeper quarantine attribute from the unzipped folder.
#   3. uv sync to materialize .venv with the required extras.
#   4. uv run streamlit run streamlit_app/app.py on port 8501.

set -e

# 1. cd to the launcher's own directory (handles double-click from Finder).
cd "$(dirname "$0")"

# 2. Clear the Gatekeeper quarantine attribute. Swallow failures — a folder
#    without the attribute is fine and should not scare the user.
xattr -dr com.apple.quarantine . 2>/dev/null || true

# Friendly failure helper: prints a message and waits for a keypress so the
# Terminal window doesn't disappear before the user can read the error.
die() {
    echo ""
    echo "ERROR: $1"
    echo ""
    read -rsn1 -p "Press any key to exit."
    echo ""
    exit 1
}

# 3. uv sync. The bundled ./uv binary is shipped alongside this launcher by
#    the release zip; P5.x downloads it per-platform.
if [ ! -x "./uv" ]; then
    die "Could not find the bundled 'uv' binary next to this launcher. The zip may be incomplete — download a fresh copy from the releases page."
fi

if ! ./uv sync --quiet --extra ui --extra cli --extra anthropic --extra openai --extra google; then
    die "Could not sync dependencies. Check your internet connection and try again."
fi

# 4. Launch Streamlit. --server.headless false opens the browser automatically.
./uv run streamlit run streamlit_app/app.py --server.port 8501 --server.headless false
