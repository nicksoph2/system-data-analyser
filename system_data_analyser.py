#!/usr/bin/env python3
"""
System Data Analyser
macOS Sequoia · Apple Silicon

Scans your Mac's System Data directories and opens an interactive
HTML report in your default browser. No extra dependencies required.

Run:  python3 system_data_analyser.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Platform guard ────────────────────────────────────────────────────────────
if sys.platform != "darwin":
    print("System Data Analyser is for macOS only.")
    sys.exit(1)


def check_full_disk_access() -> bool:
    """
    Test for Full Disk Access by attempting to list a protected directory.
    /private/var/db/diagnostics is only readable when FDA is granted to Terminal.
    """
    try:
        return len(os.listdir("/private/var/db/diagnostics")) > 0
    except (PermissionError, OSError):
        return False

HOME = Path.home()

# ── Category definitions ──────────────────────────────────────────────────────
# Each category maps to one or more filesystem paths.
# 'safe' marks categories where files are generally safe to delete.
# 'skip_level2' prevents slow recursive scans on noisy directories.

CATEGORIES = [
    {
        "id":          "caches",
        "name":        "Application Caches",
        "icon":        "⚡",
        "desc":        "Temporary files apps create to load faster. Generally safe to clear.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Caches",
            Path("/Library/Caches"),
        ],
    },
    {
        "id":          "app_support",
        "name":        "Application Support",
        "icon":        "📦",
        "desc":        "Data, settings, and resources stored by your installed apps.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Application Support",
            Path("/Library/Application Support"),
        ],
    },
    {
        "id":          "containers",
        "name":        "App Containers & Groups",
        "icon":        "🗂",
        "desc":        "Secure sandboxed storage areas where apps keep their data.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Containers",
            HOME / "Library/Group Containers",
        ],
    },
    {
        "id":          "logs",
        "name":        "Log Files",
        "icon":        "📋",
        "desc":        "Records of system and app activity. Usually safe to clear.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Logs",
            Path("/Library/Logs"),
            Path("/private/var/log"),
        ],
    },
    {
        "id":          "preferences",
        "name":        "App Preferences",
        "icon":        "⚙️",
        "desc":        "Settings and configuration files for your apps. Do not delete.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Preferences",
        ],
    },
    {
        "id":          "xcode_build",
        "name":        "Xcode Build Data",
        "icon":        "🔨",
        "desc":        "Intermediate build files created by Xcode. Safe to delete when not building.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Developer/Xcode/DerivedData",
            HOME / "Library/Developer/Xcode/Archives",
        ],
    },
    {
        "id":          "simulators",
        "name":        "iOS & watchOS Simulators",
        "icon":        "📱",
        "desc":        "Simulator runtimes for testing iPhone, iPad, and Apple Watch apps. Often very large.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Developer/CoreSimulator",
        ],
    },
    {
        "id":          "device_support",
        "name":        "Device Support Files",
        "icon":        "🔌",
        "desc":        "Files downloaded when connecting Apple devices to Xcode for debugging.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Developer/Xcode/iOS DeviceSupport",
            HOME / "Library/Developer/Xcode/watchOS DeviceSupport",
            HOME / "Library/Developer/Xcode/tvOS DeviceSupport",
            HOME / "Library/Developer/Xcode/visionOS DeviceSupport",
            HOME / "Library/Developer/Xcode/macOS DeviceSupport",
        ],
    },
    {
        "id":          "homebrew",
        "name":        "Homebrew Packages",
        "icon":        "🍺",
        "desc":        "Command-line tools and packages installed via the Homebrew package manager.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            Path("/opt/homebrew"),
        ],
    },
    {
        "id":          "temp",
        "name":        "Temporary System Files",
        "icon":        "🗑",
        "desc":        "Short-lived files the system and apps create during normal use.",
        "safe":        True,
        "skip_level2": True,   # /private/var/folders has thousands of tiny dirs
        "paths": [
            Path("/private/var/folders"),
            Path("/private/var/tmp"),
        ],
    },
    {
        "id":          "fonts",
        "name":        "Fonts",
        "icon":        "🔤",
        "desc":        "System and user-installed font files.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Fonts",
            Path("/Library/Fonts"),
        ],
    },
    {
        "id":          "plugins",
        "name":        "Plug-ins & Extensions",
        "icon":        "🔧",
        "desc":        "Browser plug-ins, Quick Look extensions, and other system add-ons.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Internet Plug-Ins",
            HOME / "Library/QuickLook",
            Path("/Library/Internet Plug-Ins"),
            Path("/Library/QuickLook"),
        ],
    },
    {
        "id":          "icloud",
        "name":        "iCloud Drive (Local Copy)",
        "icon":        "☁️",
        "desc":        "Files from iCloud Drive currently downloaded and stored on this Mac.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Mobile Documents",
        ],
    },
    {
        "id":          "dev_frameworks",
        "name":        "Developer Frameworks & SDKs",
        "icon":        "🛠",
        "desc":        "Additional developer frameworks and SDKs installed system-wide.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            Path("/Library/Developer"),
        ],
    },
    {
        "id":          "mail_downloads",
        "name":        "Mail Downloads",
        "icon":        "📧",
        "desc":        "Attachments and file previews downloaded by the Mail app.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / "Library/Containers/com.apple.mail/Data/Library/Mail Downloads",
        ],
    },
    {
        "id":          "system_databases",
        "name":        "System Databases & Diagnostics",
        "icon":        "🗄",
        "desc":        "System-level databases, crash logs, analytics, and diagnostic data maintained by macOS.",
        "safe":        False,
        "skip_level2": False,
        "paths": [
            Path("/private/var/db/diagnostics"),
            Path("/private/var/db/uuidtext"),
            Path("/private/var/db/analyticsd"),
            Path("/private/var/db/biome"),
            Path("/private/var/db/powerlog"),
        ],
    },
    {
        "id":          "dev_tool_caches",
        "name":        "Developer Tool Caches",
        "icon":        "🔩",
        "desc":        "Build caches and package registries for developer tools — npm, pip, Go, Rust/Cargo, Maven, Gradle, and Docker. Safe to clear; tools will rebuild on next use.",
        "safe":        True,
        "skip_level2": False,
        "paths": [
            HOME / ".npm",                           # npm cache
            HOME / ".cache",                         # XDG cache dir — pip, go-build, etc.
            HOME / ".cargo" / "registry" / "cache",  # Rust crate source archives
            HOME / ".cargo" / "git" / "db",          # Rust git-sourced dependencies
            HOME / ".m2"  / "repository",            # Maven local repository
            HOME / ".gradle" / "caches",             # Gradle build cache
            HOME / ".docker",                        # Docker images, volumes, buildx cache
            HOME / ".local" / "share",               # XDG data dir (many Linux-origin tools)
        ],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_size(n: int) -> str:
    if n < 0:
        return "—"
    if n == 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def du_single(path: Path) -> tuple[int, str | None]:
    """Size of a single path in bytes via du -sk. Returns (bytes, error_or_None)."""
    try:
        r = subprocess.run(
            ["du", "-sk", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode == 0 and r.stdout:
            return int(r.stdout.split()[0]) * 1024, None
        err = r.stderr.strip()
        return -1, err or "du returned non-zero exit code"
    except subprocess.TimeoutExpired:
        return -1, "Timed out reading directory size"
    except Exception as exc:
        return -1, str(exc)


def du_children(parent: Path, cap: int = 300) -> list[dict]:
    """
    Return immediate children of *parent* with sizes.
    Uses a single batched `du -sk` call for speed.
    Results are sorted largest-first.
    Items that cannot be read include an 'error' key with a human-readable reason.
    """
    try:
        entries = [
            e for e in sorted(parent.iterdir(), key=lambda e: e.name)
            if not e.is_symlink()
        ][:cap]
    except PermissionError:
        return [{
            "name": parent.name, "path": str(parent),
            "is_dir": True, "size": -1, "children": [],
            "error": "Permission denied — grant Full Disk Access to Terminal in System Settings → Privacy & Security",
        }]
    except OSError as exc:
        return [{
            "name": parent.name, "path": str(parent),
            "is_dir": True, "size": -1, "children": [],
            "error": str(exc),
        }]

    if not entries:
        return []

    sizes: dict[str, int] = {}
    # du stderr contains lines like: "du: /path: Operation not permitted"
    path_errors: dict[str, str] = {}
    try:
        r = subprocess.run(
            ["du", "-sk"] + [str(e) for e in entries],
            capture_output=True, text=True, timeout=120,
        )
        for line in r.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                try:
                    sizes[parts[1].strip()] = int(parts[0]) * 1024
                except ValueError:
                    pass
        # Parse stderr for per-path error messages
        for line in r.stderr.splitlines():
            # Format: "du: /some/path: Permission denied"
            if line.startswith("du: ") and line.count(": ") >= 2:
                rest = line[4:]
                sep = rest.rfind(": ")
                if sep > 0:
                    err_path = rest[:sep].strip()
                    err_msg  = rest[sep+2:].strip()
                    path_errors[err_path] = err_msg
    except Exception:
        pass

    items = []
    for e in entries:
        is_dir = e.is_dir(follow_symlinks=False)
        size = sizes.get(str(e), -1)
        error = path_errors.get(str(e))

        # For plain files, fall back to stat if du missed it
        if size < 0 and not is_dir:
            try:
                size = e.stat().st_size
                error = None   # stat worked, clear any du error
            except PermissionError:
                error = error or "Permission denied"
            except OSError as exc:
                error = error or str(exc)

        items.append({
            "name":     e.name,
            "path":     str(e),
            "is_dir":   is_dir,
            "size":     size,
            "children": [],
            "error":    error,
        })

    items.sort(key=lambda x: x["size"] if x["size"] >= 0 else -1, reverse=True)
    return items


# ── Scanner ───────────────────────────────────────────────────────────────────

LEVEL2_THRESHOLD = 50 * 1024 * 1024   # scan level 2 if item > 50 MB


def scan_category(cat: dict) -> dict:
    existing = [p for p in cat["paths"] if p.exists()]
    total = 0
    children = []

    for p in existing:
        p_size, p_err = du_single(p)
        if p_size >= 0:
            total += p_size

        print(f"    Listing {p} …", flush=True)

        if p_err and p_size < 0:
            # Couldn't even measure this root path
            level1 = [{
                "name":     p.name,
                "path":     str(p),
                "is_dir":   True,
                "size":     -1,
                "children": [],
                "error":    p_err,
            }]
        else:
            level1 = du_children(p)

            if not cat["skip_level2"]:
                for item in level1:
                    if item["is_dir"] and item["size"] >= LEVEL2_THRESHOLD and not item.get("error"):
                        item["children"] = du_children(Path(item["path"]))

        if len(existing) > 1:
            # Wrap in a path-labelled node when a category spans multiple roots
            children.append({
                "name":     str(p),
                "path":     str(p),
                "is_dir":   True,
                "size":     p_size,
                "children": level1,
                "error":    p_err if p_size < 0 else None,
            })
        else:
            children.extend(level1)

    return {
        "id":       cat["id"],
        "name":     cat["name"],
        "icon":     cat["icon"],
        "desc":     cat["desc"],
        "safe":     cat["safe"],
        "size":     total,
        "children": children,
    }


# ── APFS snapshot scanner ─────────────────────────────────────────────────────

def _parse_diskutil_size(text: str) -> int:
    """
    Parse a size string from diskutil output → bytes.
    Handles comma-separated raw bytes  e.g. '+26,843,545,600 B (26.8 GB)'
    and human-readable fallback         e.g. '26.8 GB'.
    Returns -1 if nothing matched.
    """
    import re
    # Prefer raw byte count (comma-formatted integer followed by lone 'B')
    m = re.search(r"[+\-]?([\d,]+)\s+B\b", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # Fall back to human-readable unit
    m = re.search(r"[+\-]?([\d.]+)\s*(KB|MB|GB|TB)", text, re.IGNORECASE)
    if m:
        val  = float(m.group(1))
        unit = m.group(2).upper()
        mul  = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return int(val * mul.get(unit, 1))
    return -1


def _get_root_apfs_device() -> str:
    """
    Return the device identifier for the APFS Data volume (e.g. 'disk3s1').
    On macOS Catalina+, Time Machine snapshots live on /System/Volumes/Data,
    NOT on the sealed System Volume that '/' resolves to.
    Falls back to '/' if the Data volume mount isn't present.
    """
    for mount in ("/System/Volumes/Data", "/"):
        try:
            r = subprocess.run(
                ["diskutil", "info", mount],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.splitlines():
                if "Device Identifier:" in line:
                    dev = line.split(":", 1)[1].strip()
                    # Prefer the plain volume (e.g. disk3s1) over a snapshot
                    # device (e.g. disk3s3s1) — snapshots have an extra segment
                    if dev.count("s") <= 2 or mount == "/":
                        return dev
        except Exception:
            pass
    return ""


def _get_per_snapshot_sizes(device: str) -> dict[str, int]:
    """
    Use 'diskutil apfs listSnapshots <device>' to get individual snapshot sizes.
    Returns {snapshot_name: bytes} for every snapshot that reports a size.
    """
    import re
    sizes: dict[str, int] = {}
    if not device:
        return sizes
    try:
        r = subprocess.run(
            ["diskutil", "apfs", "listSnapshots", device],
            capture_output=True, text=True, timeout=15,
        )
        current: str | None = None
        for line in r.stdout.splitlines():
            name_m = re.search(r"(com\.apple\.TimeMachine\.[^\s]+)", line)
            if name_m:
                current = name_m.group(1)
            elif current and "Snapshot Size:" in line:
                sz = _parse_diskutil_size(line)
                if sz > 0:
                    sizes[current] = sz
                current = None
    except Exception:
        pass
    return sizes


def _get_snapshot_total_from_apfs_list() -> int:
    """
    Fall-back: parse 'Snapshot Space Used' from 'diskutil apfs list'.
    Returns bytes or -1.
    """
    try:
        r = subprocess.run(
            ["diskutil", "apfs", "list"],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.splitlines():
            if "Snapshot Space Used" in line:
                sz = _parse_diskutil_size(line)
                if sz >= 0:
                    return sz
    except Exception:
        pass
    return -1


def scan_apfs_snapshots() -> dict:
    """
    List local Time Machine APFS snapshots and report space used.
    Snapshots are invisible to du/find — their sizes come from diskutil.
    Strategy:
      1. List names via tmutil listlocalsnapshots
      2. Get per-snapshot sizes via diskutil apfs listSnapshots <device>  ← most accurate
      3. Fall back to total from diskutil apfs list, divided evenly       ← approximate
    """
    # 1. Collect snapshot names
    snap_names: list[str] = []
    try:
        r = subprocess.run(
            ["tmutil", "listlocalsnapshots", "/"],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("com.apple.TimeMachine."):
                snap_names.append(line)
    except Exception:
        pass

    # 2. Per-snapshot sizes
    device    = _get_root_apfs_device()
    snap_sizes = _get_per_snapshot_sizes(device)

    # 3. Fall-back total
    fallback_total = -1
    if not snap_sizes:
        fallback_total = _get_snapshot_total_from_apfs_list()

    # Compute overall total
    sizes_known = False
    if snap_sizes:
        total_size = sum(snap_sizes.values())
        sizes_known = True
    elif fallback_total > 0:
        total_size = fallback_total
        sizes_known = True
    else:
        total_size = -1   # genuinely unknown — render as '—', not '0 B'

    # 4. Build children
    children = []
    for raw in snap_names:
        display = raw
        try:
            date_part = raw.split("TimeMachine.")[1].replace(".local", "")
            dt = datetime.strptime(date_part, "%Y-%m-%d-%H%M%S")
            display = f"Snapshot — {dt.strftime('%d %b %Y at %H:%M')}"
        except Exception:
            pass

        if raw in snap_sizes:
            snap_size = snap_sizes[raw]
            item_note = None
        elif fallback_total > 0 and snap_names:
            snap_size = fallback_total // len(snap_names)
            item_note = "approx."
        else:
            snap_size = -1
            item_note = None   # size shows as '—'; no warning needed

        children.append({
            "name":     display,
            "path":     raw,
            "is_dir":   False,
            "size":     snap_size,
            "children": [],
            "error":    None,        # never treat unavailable size as an error
            "note":     item_note,
        })

    sizes_note = (
        ""
        if sizes_known
        else " Individual sizes are not exposed by macOS public APIs on this version — "
             "the total shown in System Settings Storage comes from a private framework."
    )

    return {
        "id":       "apfs_snapshots",
        "name":     "Time Machine Local Snapshots",
        "icon":     "⏱",
        "desc":     (
            "Local APFS snapshots created by Time Machine. "
            "Invisible to normal disk tools (du/find) and often account for many GB of 'System Data'."
            + sizes_note
        ),
        "safe":     True,
        "size":     total_size,
        "children": children,
    }


# ── HTML generator ────────────────────────────────────────────────────────────

def generate_html(results: list[dict], grand_total: int, scan_time: str,
                  fda: bool = False) -> str:
    data_json      = json.dumps(results, ensure_ascii=False)
    total_str      = fmt_size(grand_total)
    total_bytes    = grand_total
    fda_badge      = (
        '<span class="fda-badge fda-ok">✓ Full Disk Access</span>'
        if fda else
        '<span class="fda-badge fda-warn">⚠ Limited Access</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>System Data Report</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  background: #f5f5f7;
  color: #1d1d1f;
  min-height: 100vh;
}}

/* ── Header ── */
header {{
  background: rgba(255,255,255,0.85);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid #d2d2d7;
  padding: 20px 32px;
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}}

header h1 {{
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
}}

.header-meta {{
  font-size: 13px;
  color: #6e6e73;
  text-align: right;
  line-height: 1.6;
}}

.header-total {{
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
}}

/* ── Main layout ── */
main {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 28px 24px 60px;
}}

/* ── Hint bar ── */
.hint {{
  background: #fff9e6;
  border: 1px solid #f0d060;
  border-radius: 10px;
  padding: 11px 16px;
  font-size: 13px;
  color: #5a4500;
  margin-bottom: 24px;
  line-height: 1.5;
}}

/* ── Category cards ── */
.category {{
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.06);
  margin-bottom: 16px;
  overflow: hidden;
}}

.cat-header {{
  display: flex;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
  gap: 14px;
}}

.cat-header:hover {{
  background: #f9f9fb;
}}

.cat-toggle {{
  font-size: 11px;
  color: #aeaeb2;
  transition: transform 0.2s;
  flex-shrink: 0;
  width: 14px;
}}

.cat-toggle.open {{
  transform: rotate(90deg);
}}

.cat-icon {{
  font-size: 22px;
  flex-shrink: 0;
  line-height: 1;
}}

.cat-info {{
  flex: 1;
  min-width: 0;
}}

.cat-name {{
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}}

.fda-badge {{
  font-size: 12px;
  font-weight: 500;
  border-radius: 20px;
  padding: 2px 10px;
  white-space: nowrap;
}}
.fda-ok {{
  background: #e8f9ee;
  color: #1a7f37;
}}
.fda-warn {{
  background: #fff3e0;
  color: #b45309;
}}

.safe-badge {{
  font-size: 11px;
  font-weight: 500;
  background: #e8f9ee;
  color: #1a7f37;
  border-radius: 20px;
  padding: 1px 8px;
}}

.cat-desc {{
  font-size: 12px;
  color: #6e6e73;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.cat-right {{
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  gap: 5px;
}}

.cat-size {{
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}}

.size-bar-track {{
  width: 120px;
  height: 5px;
  background: #e5e5ea;
  border-radius: 99px;
  overflow: hidden;
}}

.size-bar-fill {{
  height: 100%;
  border-radius: 99px;
  transition: width 0.4s ease;
}}

/* ── Tree ── */
.tree-body {{
  display: none;
  border-top: 1px solid #f0f0f5;
}}

.tree-body.open {{
  display: block;
}}

.tree-item {{
  border-bottom: 1px solid #f5f5f7;
}}

.tree-item:last-child {{
  border-bottom: none;
}}

.item-row {{
  display: flex;
  align-items: center;
  padding: 9px 20px;
  cursor: default;
  gap: 8px;
  font-size: 13px;
}}

.item-row:hover {{
  background: #f5f5f7;
}}

.item-row.has-children {{
  cursor: pointer;
}}

.item-toggle {{
  font-size: 10px;
  color: #aeaeb2;
  width: 14px;
  flex-shrink: 0;
  transition: transform 0.15s;
}}

.item-toggle.open {{
  transform: rotate(90deg);
}}

.item-toggle-placeholder {{
  width: 14px;
  flex-shrink: 0;
}}

.item-icon {{
  font-size: 15px;
  flex-shrink: 0;
  line-height: 1;
}}

.item-name {{
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}

.item-size {{
  font-size: 12px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  min-width: 70px;
  text-align: right;
}}

.item-path {{
  font-size: 11px;
  color: #aeaeb2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
  flex-shrink: 1;
}}

.copy-btn {{
  background: none;
  border: 1px solid #d2d2d7;
  border-radius: 5px;
  padding: 2px 8px;
  font-size: 11px;
  color: #0071e3;
  cursor: pointer;
  flex-shrink: 0;
  display: none;
  white-space: nowrap;
}}

.item-row:hover .copy-btn {{
  display: inline-block;
}}

.copy-btn:hover {{
  background: #0071e3;
  color: white;
  border-color: #0071e3;
}}

.children-container {{
  display: none;
}}

.children-container.open {{
  display: block;
}}

.indent {{
  padding-left: 28px;
}}

/* ── Size colours ── */
.sz-huge   {{ color: #c0392b; }}
.sz-large  {{ color: #d35400; }}
.sz-medium {{ color: #b7950b; }}
.sz-small  {{ color: #1e8449; }}
.sz-tiny   {{ color: #7f8c8d; }}

.bar-huge   {{ background: #e74c3c; }}
.bar-large  {{ background: #e67e22; }}
.bar-medium {{ background: #f1c40f; }}
.bar-small  {{ background: #2ecc71; }}
.bar-tiny   {{ background: #bdc3c7; }}

/* ── Empty / no access ── */
.no-data {{
  padding: 14px 20px;
  font-size: 13px;
  color: #aeaeb2;
  font-style: italic;
}}

/* ── Error items ── */
.item-row.error-row {{
  background: #fff8f0;
}}
.item-row.error-row:hover {{
  background: #fff3e6;
}}
.error-icon {{
  font-size: 14px;
  flex-shrink: 0;
}}
.error-reason {{
  font-size: 11px;
  color: #c0392b;
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}}
.item-note {{
  font-size: 11px;
  color: #888;
  font-style: italic;
  margin-left: 6px;
  flex-shrink: 0;
}}
.error-badge {{
  font-size: 11px;
  font-weight: 500;
  background: #fdecea;
  color: #c0392b;
  border-radius: 20px;
  padding: 1px 8px;
  margin-left: 6px;
  white-space: nowrap;
}}

/* ── Footer ── */
footer {{
  text-align: center;
  font-size: 12px;
  color: #aeaeb2;
  padding: 24px;
}}
</style>
</head>
<body>

<header>
  <h1>🖥 System Data Analyser</h1>
  <div class="header-meta">
    <div class="header-total" id="grand-total">Total: {total_str}</div>
    <div>{fda_badge} &nbsp; Scanned {scan_time}</div>
  </div>
</header>

<main>
  <div class="hint">
    💡 <strong>Click any row</strong> to expand and see what's inside.&nbsp;
    Hover over an item and click <strong>Copy Path</strong> to copy its location —
    then paste into Finder's <em>Go → Go to Folder…</em> (⌘⇧G) to open it directly.&nbsp;
    <span style="color:#1a7f37">✓ Safe to clear</span> categories can generally be deleted without harm.
  </div>

  <div id="categories"></div>
</main>

<footer>System Data Analyser · {scan_time}</footer>

<script>
const DATA = {data_json};
const GRAND_TOTAL = {total_bytes};

// ── Utilities ──────────────────────────────────────────────────────────────

function fmtSize(n) {{
  if (n < 0) return '—';
  if (n === 0) return '0 B';
  const units = ['B','KB','MB','GB','TB'];
  for (const u of units) {{
    if (n < 1024) return n.toFixed(1) + ' ' + u;
    n /= 1024;
  }}
  return n.toFixed(1) + ' PB';
}}

function sizeClass(n) {{
  if (n >= 10  * 1024**3) return 'huge';
  if (n >= 1   * 1024**3) return 'large';
  if (n >= 100 * 1024**2) return 'medium';
  if (n >= 10  * 1024**2) return 'small';
  return 'tiny';
}}

function barWidth(n) {{
  if (!GRAND_TOTAL || n <= 0) return 0;
  return Math.min(100, Math.round((n / GRAND_TOTAL) * 100));
}}

function fileIcon(name, isDir) {{
  if (isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  const map = {{
    app:'📱', dmg:'💿', pkg:'📦', pdf:'📄',
    doc:'📝', docx:'📝', xls:'📊', xlsx:'📊', csv:'📊',
    zip:'🗜', tar:'🗜', gz:'🗜', '7z':'🗜',
    log:'📋', txt:'📄', py:'🐍', js:'📜', ts:'📜',
    swift:'🦅', m:'📄', h:'📄',
    png:'🖼', jpg:'🖼', jpeg:'🖼', gif:'🖼', heic:'🖼',
    mp4:'🎬', mov:'🎬', mp3:'🎵', m4a:'🎵',
    ttf:'🔤', otf:'🔤', woff:'🔤', woff2:'🔤',
    plist:'📋', db:'🗄', sqlite:'🗄',
  }};
  return map[ext] || '📄';
}}

function copyPath(path, btn) {{
  navigator.clipboard.writeText(path).then(() => {{
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    btn.style.color = '#34c759';
    btn.style.borderColor = '#34c759';
    setTimeout(() => {{
      btn.textContent = orig;
      btn.style.color = '';
      btn.style.borderColor = '';
    }}, 1500);
  }});
}}

// ── Tree renderer ──────────────────────────────────────────────────────────

function countErrors(items) {{
  let n = 0;
  if (!items) return 0;
  for (const item of items) {{
    if (item.error) n++;
    n += countErrors(item.children);
  }}
  return n;
}}

function makeItemRow(item, depth) {{
  const hasChildren = item.is_dir && item.children && item.children.length > 0;
  const sc = sizeClass(item.size);
  const isError = !!item.error;

  const row = document.createElement('div');
  row.className = 'item-row' + (hasChildren ? ' has-children' : '') + (isError ? ' error-row' : '');
  row.style.paddingLeft = (20 + depth * 22) + 'px';

  // Toggle arrow
  if (hasChildren) {{
    const tog = document.createElement('span');
    tog.className = 'item-toggle';
    tog.textContent = '▶';
    row.appendChild(tog);
  }} else {{
    const ph = document.createElement('span');
    ph.className = 'item-toggle-placeholder';
    row.appendChild(ph);
  }}

  // Icon — warning triangle for errors
  const icon = document.createElement('span');
  icon.className = isError ? 'error-icon' : 'item-icon';
  icon.textContent = isError ? '⚠️' : fileIcon(item.name, item.is_dir);
  row.appendChild(icon);

  // Name
  const name = document.createElement('span');
  name.className = 'item-name';
  name.textContent = item.name;
  name.title = item.path;
  row.appendChild(name);

  if (isError) {{
    // Show the error reason instead of size + path columns
    const reason = document.createElement('span');
    reason.className = 'error-reason';
    reason.textContent = item.error;
    reason.title = item.error;
    row.appendChild(reason);
  }} else {{
    // Size
    const sz = document.createElement('span');
    sz.className = 'item-size sz-' + sc;
    sz.textContent = fmtSize(item.size);
    row.appendChild(sz);

    // Optional note (e.g. "approx.") — shown in muted italic after size
    if (item.note) {{
      const noteEl = document.createElement('span');
      noteEl.className = 'item-note';
      noteEl.textContent = item.note;
      row.appendChild(noteEl);
    }}

    // Path (truncated)
    const pathSpan = document.createElement('span');
    pathSpan.className = 'item-path';
    pathSpan.textContent = item.path;
    pathSpan.title = item.path;
    row.appendChild(pathSpan);

    // Copy button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = 'Copy Path';
    copyBtn.onclick = (e) => {{ e.stopPropagation(); copyPath(item.path, copyBtn); }};
    row.appendChild(copyBtn);
  }}

  // Build children container
  const container = document.createElement('div');
  container.className = 'children-container';

  if (hasChildren) {{
    item.children.forEach(child => {{
      const childEl = makeItemRow(child, depth + 1);
      container.appendChild(childEl);
    }});

    // Toggle expand on click
    row.addEventListener('click', () => {{
      const isOpen = container.classList.toggle('open');
      const togEl = row.querySelector('.item-toggle');
      if (togEl) togEl.classList.toggle('open', isOpen);
    }});
  }}

  // Wrap row + children in a wrapper div
  const wrapper = document.createElement('div');
  wrapper.className = 'tree-item';
  wrapper.appendChild(row);
  wrapper.appendChild(container);
  return wrapper;
}}

// ── Category renderer ──────────────────────────────────────────────────────

function renderCategory(cat) {{
  const sc   = sizeClass(cat.size);
  const bw   = barWidth(cat.size);
  const safe = cat.safe && cat.size > 0;

  const card = document.createElement('div');
  card.className = 'category';

  // Header row
  const hdr = document.createElement('div');
  hdr.className = 'cat-header';

  const toggle = document.createElement('span');
  toggle.className = 'cat-toggle';
  toggle.textContent = '▶';

  const icon = document.createElement('span');
  icon.className = 'cat-icon';
  icon.textContent = cat.icon;

  const info = document.createElement('div');
  info.className = 'cat-info';

  const nameLine = document.createElement('div');
  nameLine.className = 'cat-name';
  nameLine.textContent = cat.name;
  if (safe) {{
    const badge = document.createElement('span');
    badge.className = 'safe-badge';
    badge.textContent = '✓ Safe to clear';
    nameLine.appendChild(badge);
  }}
  const errCount = countErrors(cat.children);
  if (errCount > 0) {{
    const errBadge = document.createElement('span');
    errBadge.className = 'error-badge';
    errBadge.textContent = '⚠️ ' + errCount + ' unreadable';
    errBadge.title = errCount + ' item' + (errCount === 1 ? '' : 's') + ' could not be read — expand to see details';
    nameLine.appendChild(errBadge);
  }}

  const desc = document.createElement('div');
  desc.className = 'cat-desc';
  desc.textContent = cat.desc;

  info.appendChild(nameLine);
  info.appendChild(desc);

  const right = document.createElement('div');
  right.className = 'cat-right';

  const sizeLbl = document.createElement('div');
  sizeLbl.className = 'cat-size sz-' + sc;
  sizeLbl.textContent = fmtSize(cat.size);

  const track = document.createElement('div');
  track.className = 'size-bar-track';
  const fill = document.createElement('div');
  fill.className = 'size-bar-fill bar-' + sc;
  fill.style.width = bw + '%';
  track.appendChild(fill);

  right.appendChild(sizeLbl);
  right.appendChild(track);

  hdr.appendChild(toggle);
  hdr.appendChild(icon);
  hdr.appendChild(info);
  hdr.appendChild(right);

  // Tree body
  const body = document.createElement('div');
  body.className = 'tree-body';

  if (cat.children && cat.children.length > 0) {{
    cat.children.forEach(item => {{
      body.appendChild(makeItemRow(item, 0));
    }});
  }} else {{
    const nd = document.createElement('div');
    nd.className = 'no-data';
    nd.textContent = cat.size <= 0
      ? 'Not found or no permission to read this folder.'
      : 'No items to display.';
    body.appendChild(nd);
  }}

  // Toggle
  hdr.addEventListener('click', () => {{
    const open = body.classList.toggle('open');
    toggle.classList.toggle('open', open);
  }});

  card.appendChild(hdr);
  card.appendChild(body);
  return card;
}}

// ── Bootstrap ─────────────────────────────────────────────────────────────

(function() {{
  const container = document.getElementById('categories');
  DATA.forEach(cat => container.appendChild(renderCategory(cat)));
}})();
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

# ── Spotlight large-file scanner ──────────────────────────────────────────────

# Paths already covered by the main category scanner — excluded from the
# Spotlight scan to avoid counting the same bytes twice.
_SPOTLIGHT_EXCLUDE: tuple[Path, ...] = (
    HOME / "Library",
    HOME / ".npm",
    HOME / ".cache",
    HOME / ".cargo",
    HOME / ".m2",
    HOME / ".gradle",
    HOME / ".docker",
    HOME / ".local",
)

def scan_large_files_spotlight(min_bytes: int = 100 * 1024 * 1024) -> dict:
    """
    Use Spotlight (mdfind) to find files >= min_bytes in the user's home
    directory that are NOT already covered by the main category scanner.
    This surfaces large orphaned files — disk images, archives, old backups,
    media files — that would otherwise be invisible to a directory-tree scan.
    """
    children: list[dict] = []
    total_size = 0

    try:
        r = subprocess.run(
            [
                "mdfind",
                "-onlyin", str(HOME),
                f"kMDItemFSSize >= {min_bytes}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        seen: set[str] = set()
        for line in r.stdout.splitlines():
            p_str = line.strip()
            if not p_str or p_str in seen:
                continue
            seen.add(p_str)
            p = Path(p_str)
            # Skip anything already counted by the category scanner
            if any(
                p == excl or str(p).startswith(str(excl) + "/")
                for excl in _SPOTLIGHT_EXCLUDE
            ):
                continue
            try:
                st = p.stat()
                # st_blocks is the number of 512-byte blocks actually allocated on
                # disk.  iCloud files that are stored only in the cloud (not
                # downloaded) show a non-zero st_size reported by Spotlight but
                # have st_blocks == 0 — no local storage used at all.  Skip them.
                if st.st_blocks == 0:
                    continue
                sz = st.st_size
            except OSError:
                continue
            children.append({
                "name":     p.name,
                "path":     p_str,
                "is_dir":   False,
                "size":     sz,
                "children": [],
                "error":    None,
                "note":     None,
            })
            total_size += sz

        # Sort largest first, cap at 200 items to keep the report readable
        children.sort(key=lambda x: x["size"], reverse=True)
        children = children[:200]

    except Exception:
        pass

    count = len(children)
    desc = (
        f"Files over 100 MB found by Spotlight outside scanned Library directories — "
        f"disk images, archives, old backups, large media, and similar. "
        f"{count} file{'s' if count != 1 else ''} found."
    )

    return {
        "id":       "large_files_spotlight",
        "name":     "Large Files (Spotlight)",
        "icon":     "🔍",
        "desc":     desc,
        "safe":     False,
        "size":     total_size,
        "children": children,
    }


def main() -> None:
    print("")
    print("  System Data Analyser")
    print("  " + "─" * 38)
    print("")

    # FDA status: launcher passes "granted" or "missing" as argv[1].
    # If run directly (no arg), check here ourselves.
    if len(sys.argv) > 1 and sys.argv[1] == "granted":
        fda = True
    elif len(sys.argv) > 1 and sys.argv[1] == "missing":
        fda = False
    else:
        fda = check_full_disk_access()

    if fda:
        print("  ✓ Full Disk Access confirmed")
    else:
        print("  ⚠  No Full Disk Access — some directories will show permission errors")
        print("     System Settings → Privacy & Security → Full Disk Access → enable Terminal")
    print("")

    scan_time = datetime.now().strftime("%d %B %Y at %H:%M")
    results: list[dict] = []

    for cat in CATEGORIES:
        print(f"  {cat['icon']}  Scanning {cat['name']} …", flush=True)
        result = scan_category(cat)
        results.append(result)
        print(f"      → {fmt_size(result['size'])}", flush=True)

    # APFS snapshots require tmutil/diskutil — handled separately from CATEGORIES
    print("  ⏱  Scanning Time Machine Local Snapshots …", flush=True)
    snap_result = scan_apfs_snapshots()
    results.append(snap_result)
    print(f"      → {fmt_size(snap_result['size'])}", flush=True)

    # Spotlight scan for large files outside already-scanned directories
    print("  🔍  Scanning for large files via Spotlight …", flush=True)
    spotlight_result = scan_large_files_spotlight()
    results.append(spotlight_result)
    count = len(spotlight_result["children"])
    print(f"      → {fmt_size(spotlight_result['size'])} ({count} files)", flush=True)

    grand_total = sum(max(0, r["size"]) for r in results)

    print("")
    print(f"  Grand total: {fmt_size(grand_total)}")
    print("")
    print("  Generating report …", flush=True)

    html = generate_html(results, grand_total, scan_time, fda=fda)

    # Save to ~/Downloads with a timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    out_path = downloads / f"system_data_{timestamp}.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"  Report saved to: {out_path}")
    print("  Opening in browser …")
    print("")
    subprocess.run(["open", str(out_path)])


if __name__ == "__main__":
    main()
