#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# System Data Analyser — Launcher
# Double-click this file in Finder to open the app.
# ─────────────────────────────────────────────────────────────────────────────
cd "$(dirname "$0")"

echo ""
echo "  System Data Analyser"
echo "  ──────────────────────────────────────────"
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

echo "  Python: $PYTHON  ($VERSION)"
echo ""

# ── Full Disk Access check ────────────────────────────────────────────────────
# /private/var/db/diagnostics is only readable with Full Disk Access granted
# to the Terminal. We use it as a reliable proxy to test FDA status.

check_fda() {
    ls /private/var/db/diagnostics &>/dev/null 2>&1
}

echo "  Checking Full Disk Access…"

if check_fda; then
    echo "  ✓ Full Disk Access confirmed — all directories will be scanned"
    FDA_STATUS="granted"
else
    echo "  ⚠  Full Disk Access not detected"
    FDA_STATUS="missing"

    # Ask the user what they want to do
    CHOICE=$(osascript <<'APPLESCRIPT'
button returned of (display alert "Full Disk Access Recommended" message "System Data Analyser works best with Full Disk Access granted to Terminal.

Without it, system directories like diagnostics databases and some caches cannot be read, and the total size reported will be lower than macOS shows.

Would you like to open System Settings to grant access now?" buttons {"Continue Anyway", "Open System Settings"} default button "Open System Settings" as informational)
APPLESCRIPT
    )

    if [ "$CHOICE" = "Open System Settings" ]; then
        # Open directly to the Full Disk Access pane
        open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"

        # Prompt the user to grant access and click OK when done
        osascript <<'APPLESCRIPT'
display alert "Grant Full Disk Access to Terminal" message "In System Settings:

1. Scroll down to find Terminal in the list
2. Toggle it ON
3. You may be asked to quit and reopen Terminal
4. Once done, click OK to continue" buttons {"OK"} default button "OK"
APPLESCRIPT

        # Re-check after the user has had a chance to grant access
        if check_fda; then
            echo "  ✓ Full Disk Access confirmed — thank you!"
            FDA_STATUS="granted"
        else
            echo "  ⚠  Full Disk Access still not detected — you may need to reopen Terminal after granting access"
            echo "     The scan will continue but some directories may show permission errors"
            FDA_STATUS="missing"
        fi
    else
        echo "  Continuing without Full Disk Access — some areas may show permission errors"
    fi
fi

echo ""

# ── Run ───────────────────────────────────────────────────────────────────────
"$PYTHON" system_data_analyser.py "$FDA_STATUS"

echo ""
echo "  Done. You can close this window."
