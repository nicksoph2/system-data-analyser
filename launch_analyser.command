#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# System Data Analyser — Launcher
# Double-click this file in Finder to open the app.
# ─────────────────────────────────────────────────────────────────────────────
cd "$(dirname "$0")"

echo ""
echo "  System Data Analyser — finding Python…"
echo ""

# ── Find a working Python 3 ───────────────────────────────────────────────────
# The python3 from python.org bundles an old Tk framework that crashes on
# macOS Sequoia before any code runs. We try Homebrew's Python first, which
# does not have this issue, then fall back through other common locations.

PYTHON=""

# Build candidate list — /usr/bin/python3 is a macOS stub that lies about
# being executable and sometimes even passes a quick -c test, so we skip it.
CANDIDATES=(
    /opt/homebrew/bin/python3
    /opt/homebrew/opt/python@3.13/bin/python3
    /opt/homebrew/opt/python@3.12/bin/python3
    /opt/homebrew/opt/python@3.11/bin/python3
    /usr/local/bin/python3
)

# Also try whatever `which python3` resolves to, unless it is the macOS stub
WHICH_PY="$( (which python3) 2>/dev/null )"
if [ -n "$WHICH_PY" ] && [ "$WHICH_PY" != "/usr/bin/python3" ]; then
    CANDIDATES+=( "$WHICH_PY" )
fi

for candidate in "${CANDIDATES[@]}"; do
    # Must be a real, executable regular file (not a stub/shim)
    [ -f "$candidate" ] && [ -x "$candidate" ] || continue

    # Skip the macOS Xcode CLT stub — it lies
    [ "$candidate" = "/usr/bin/python3" ] && continue

    # Test that this Python actually starts and can print its version
    VERSION=$("$candidate" --version 2>&1) || continue
    echo "  Found: $candidate  ($VERSION)"

    # Confirm it can run a tiny script without crashing
    if "$candidate" -c "import sys; sys.exit(0)" 2>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

# ── If no working Python found, offer to install via Homebrew ─────────────────
if [ -z "$PYTHON" ]; then
    if command -v brew &>/dev/null || [ -x /opt/homebrew/bin/brew ]; then
        BREW="$( (command -v brew || echo /opt/homebrew/bin/brew) )"
        RESULT=$(osascript -e 'button returned of (display alert "Python 3 Needed" message "No working Python 3 was found on your Mac.\n\nThis is usually caused by a Python.org install that is incompatible with macOS Sequoia.\n\nWould you like to install a compatible version now via Homebrew? This takes about a minute." buttons {"Cancel", "Install Python via Homebrew"} default button "Install Python via Homebrew")')
        if [ "$RESULT" = "Install Python via Homebrew" ]; then
            echo "  Installing Python 3 via Homebrew (this may take a moment)…"
            "$BREW" install python3
            PYTHON="/opt/homebrew/bin/python3"
        else
            echo "  Cancelled."
            exit 0
        fi
    else
        osascript -e 'display alert "Python 3 Needed" message "No working Python 3 was found on your Mac.\n\nThe easiest fix is to install Homebrew, then run:\n\n  brew install python3\n\nVisit https://brew.sh for Homebrew install instructions." as critical'
        exit 1
    fi
fi

echo "  Using: $PYTHON  ($VERSION)"
echo ""

# ── One-time Full Disk Access reminder ────────────────────────────────────────
PREF="$HOME/.config/sda_fda_shown"
if [ ! -f "$PREF" ]; then
    osascript -e 'display alert "Tip: Full Disk Access" message "For the most complete results, grant Full Disk Access to Terminal.\n\nSystem Settings → Privacy & Security → Full Disk Access\n\nYou only need to do this once. The app works without it, but a few system folders may show limited data." as informational buttons {"OK"}' &>/dev/null
    mkdir -p "$(dirname "$PREF")" && touch "$PREF"
fi

# ── Run ───────────────────────────────────────────────────────────────────────
"$PYTHON" system_data_analyser.py

echo ""
echo "  Done. You can close this window."
