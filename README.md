# System Data Analyser

A lightweight macOS tool that scans the directories contributing to the **System Data** category in _System Settings → General → Storage_ and produces a clean, interactive HTML report — no installs, no dependencies beyond Python 3.

![macOS](https://img.shields.io/badge/macOS-Sequoia%2015%2B-blue) ![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen) ![Architecture](https://img.shields.io/badge/Architecture-Apple%20Silicon-orange) ![Licence](https://img.shields.io/badge/Licence-MIT-lightgrey)

---

## What it does

macOS bundles a wide range of files into a catch-all _System Data_ bucket that gives no insight into what is actually consuming the space. System Data Analyser breaks that bucket open by scanning 15 categories of directories and presenting the results in a clear, drillable report saved to your Downloads folder.

The report opens automatically in your default browser. Categories are shown with their total size and a proportional bar chart. Clicking any row expands it to reveal the subdirectories and files inside, each with its individual size. A **Copy Path** button on hover lets you jump straight to any folder in Finder via _Go → Go to Folder…_ (⌘⇧G).

### Categories scanned

| Icon | Category                    | Description                                             |
| ---- | --------------------------- | ------------------------------------------------------- |
| ⚡   | Application Caches          | Temporary files apps create to speed up loading         |
| 📦   | Application Support         | Data and resources stored by installed apps             |
| 🗂   | App Containers & Groups     | Sandboxed storage areas for apps                        |
| 📋   | Log Files                   | System and application activity logs                    |
| ⚙️   | App Preferences             | Configuration files for your apps                       |
| 🔨   | Xcode Build Data            | Intermediate build files and archives                   |
| 📱   | iOS & watchOS Simulators    | Simulator runtimes for device testing                   |
| 🔌   | Device Support Files        | Files downloaded when connecting Apple devices to Xcode |
| 🍺   | Homebrew Packages           | Command-line tools installed via Homebrew               |
| 🗑   | Temporary System Files      | Short-lived files created during normal use             |
| 🔤   | Fonts                       | System and user-installed font files                    |
| 🔧   | Plug-ins & Extensions       | Browser plug-ins, Quick Look extensions, and add-ons    |
| ☁️   | iCloud Drive (Local Copy)   | iCloud files currently downloaded to this Mac           |
| 🛠   | Developer Frameworks & SDKs | Additional developer frameworks installed system-wide   |
| 📧   | Mail Downloads              | Attachments and previews downloaded by Mail             |

### Error visibility

Directories that cannot be read are shown inline in the report — highlighted in amber with a ⚠️ icon and the specific reason (e.g. _Permission denied_). Categories with unreadable items display an `⚠️ N unreadable` badge on their header row. Granting Full Disk Access to Terminal in _System Settings → Privacy & Security → Full Disk Access_ resolves most permission errors.

---

## Why the total may differ from macOS Storage

If you compare this tool's grand total with the **System Data** figure in _System Settings → General → Storage_, you will almost certainly see a gap — often anywhere from a few GB to 30 GB or more. This is expected and has two main causes.

### 1 · APFS local Time Machine snapshots

When Time Machine is active, macOS keeps rolling local snapshots of your Data volume directly on the internal drive. These are stored as **APFS snapshot metadata** — they are completely invisible to standard file-system tools like `du`, `find`, and `ls`. Apple's Storage panel reads their sizes via a private APFS framework that is not accessible to third-party tools.

System Data Analyser detects these snapshots and lists them by date, but cannot report their individual sizes. On a Mac with a few recent snapshots, this alone can account for 15–30 GB of unexplained space.

**What you can do manually:**

```bash
# List your local snapshots with their names and dates
tmutil listlocalsnapshots /

# See full details (UUID, XID, purgeable flag) for each snapshot on the Data volume
diskutil apfs listSnapshots disk3s1
# Replace disk3s1 with your Data volume if different —
# run: diskutil info /System/Volumes/Data | grep "Device Identifier"

# Check how much total space the APFS container has allocated vs free
diskutil apfs list | grep -E "Capacity|Size"
```

Snapshots are automatically purged by macOS when disk space runs low. To reclaim the space immediately without deleting them yourself, you can use Disk Utility's First Aid, or delete them explicitly (this is safe — Time Machine will create new ones at the next backup):

```bash
# Delete ALL local snapshots — macOS will recreate them at the next backup
sudo tmutil deletelocalsnapshots /

# Or delete a single named snapshot
sudo tmutil deletelocalsnapshot com.apple.TimeMachine.YYYY-MM-DD-HHMMSS.local
```

### 2 · System-protected databases (`/private/var/db/`)

macOS stores a significant amount of diagnostic and analytics data in `/private/var/db/`. These directories — including `diagnostics`, `uuidtext`, `analyticsd`, `biome`, and `powerlog` — are **only readable with Full Disk Access granted to Terminal**. Without it, they are silently skipped or show a permission error.

System Data Analyser includes a "System Databases" category that scans these paths when Full Disk Access is available (typically 2–5 GB combined). Without FDA they appear as errors or are omitted entirely.

**What you can do manually:**

```bash
# Check sizes of the main system database directories
sudo du -sh /private/var/db/diagnostics
sudo du -sh /private/var/db/uuidtext
sudo du -sh /private/var/db/analyticsd
sudo du -sh /private/var/db/biome
sudo du -sh /private/var/db/powerlog
```

### 3 · Other areas that may contribute

A smaller number of other factors can contribute to the gap:

- **Spotlight indexes** — stored at `/.Spotlight-V100`, readable only with `sudo`:

  ```bash
  sudo du -sh /.Spotlight-V100
  ```

- **APFS volume overhead** — the file system allocates space in fixed-size chunks; the difference between logical file size and allocated blocks isn't visible to `du`.

- **`/private/var/folders/`** — per-user temporary caches for sandboxed apps. Requires Full Disk Access to read fully. Grant FDA to Terminal (see Requirements) and re-run the tool for complete coverage.

- **Virtual memory swap** — located at `/private/var/vm/`, already included in the _Temporary System Files_ category if Full Disk Access is granted.

### In summary

| Source                   | Typically | Visible to this tool?      | Workaround                         |
| ------------------------ | --------- | -------------------------- | ---------------------------------- |
| APFS local TM snapshots  | 5–30 GB   | Listed, not sized          | `tmutil`/`diskutil` commands above |
| System databases         | 2–5 GB    | Yes, with Full Disk Access | Grant FDA to Terminal              |
| Spotlight index          | 0.5–3 GB  | No (needs sudo)            | `sudo du -sh /.Spotlight-V100`     |
| APFS allocation overhead | 0.5–2 GB  | No                         | Informational only                 |
| Sandboxed temp caches    | 1–5 GB    | Partially, with FDA        | Grant FDA to Terminal              |

---

## What it does NOT do

**System Data Analyser is intentionally read-only.** It scans and reports — it does not move, modify, or delete any files. This is a deliberate design decision: safe deletion requires understanding context (some caches are actively in use, some simulator runtimes are still needed), and that judgement should remain with the user.

Deletion capability may be added by somebody who understands the code and the issues better than me, the author of this sentence.

---

## Requirements

| Requirement      | Detail                                                              |
| ---------------- | ------------------------------------------------------------------- |
| **macOS**        | Sequoia 15 or later                                                 |
| **Architecture** | Apple Silicon (M-series)                                            |
| **Python**       | 3.8 or later — Homebrew Python recommended (`brew install python3`) |

> **Important:** The Python.org installer bundles an outdated Tcl/Tk framework that crashes at startup on macOS Sequoia before any code runs. Use Homebrew Python to avoid this. The launcher script (`launch_analyser.command`) detects and prefers Homebrew Python automatically.

### Optional: Full Disk Access

Without Full Disk Access, some system-owned directories (e.g. `/private/var/folders`) cannot be read. The tool works without it but shows ⚠️ errors for those locations. To grant access:

_System Settings → Privacy & Security → Full Disk Access → enable Terminal_

---

## Installation

No installation is required. Clone the repository and run the launcher:

```bash
git clone https://github.com/nicksoph2/system-data-analyser.git
cd system-data-analyser
```

### Make the launcher executable

Git preserves file permissions, so the launcher should already be executable after cloning. You can confirm this with:

```bash
git ls-files --stage launch_analyser.command
```

The mode at the start of the output should read `100755`. If it shows `100644` instead, set the executable bit manually:

```bash
chmod +x launch_analyser.command
```

### macOS Gatekeeper

macOS quarantines files downloaded from the internet, including files cloned from GitHub. The first time you run the launcher you may see _"cannot be opened because it is from an unidentified developer"_. To clear the quarantine flag:

```bash
xattr -d com.apple.quarantine launch_analyser.command
```

Or right-click the file in Finder and choose **Open**, then confirm in the dialog that appears.

### Run

```bash
./launch_analyser.command
```

---

## Files

```
system-data-analyser/
├── system_data_analyser.py   # Main scanner and HTML report generator
├── launch_analyser.command   # Launcher — finds a compatible Python and runs the app
└── README.md
```

---

## How it works

### Python launcher (`launch_analyser.command`)

The launcher is a bash script that searches for a working Python 3 installation in order of preference:

1. `/opt/homebrew/bin/python3` (Homebrew — recommended)
2. Versioned Homebrew paths (`python@3.13`, `3.12`, `3.11`)
3. `/usr/local/bin/python3`
4. Whatever `which python3` resolves to (excluding `/usr/bin/python3`, which is a macOS stub)

The macOS stub at `/usr/bin/python3` is explicitly excluded: it passes superficial existence tests but fails when invoked directly and has an incompatible Tcl/Tk framework linked to it. If no working Python is found, the launcher offers to install one via Homebrew.

### Scanner (`system_data_analyser.py`)

The scanner uses `du -sk` (disk usage in 1 KB blocks) via batched subprocess calls — grouping all children of a directory into a single `du` invocation — for speed. It operates in two levels:

- **Level 1**: sizes for the immediate children of each category root
- **Level 2**: sizes for children of any Level 1 directory larger than 50 MB

Errors from `du` are captured from stderr and attached to the relevant items. `PermissionError` and `OSError` exceptions from `Path.iterdir()` are also caught and surfaced as inline error items rather than silently swallowed.

### Report

The scanner produces a self-contained HTML file with all data embedded as JSON. A small vanilla JavaScript renderer builds the interactive tree in the browser — no frameworks, no network requests, no dependencies. The report is saved to `~/Downloads/system_data_YYYY-MM-DD_HH-MM-SS.html` and opened automatically.

---

## Development

This tool was developed collaboratively with [Claude](https://claude.ai) (Anthropic) using Cowork mode — an agentic desktop assistant that can write, run, and iterate on code directly. The development process involved:

- **Research**: Claude explored macOS System Data directories, identifying which paths contribute to the storage category and which require elevated permissions
- **Iterative debugging**: Several compatibility issues were diagnosed and fixed in session, including Python type hint syntax for older Python versions, Tcl/Tk framework crashes on macOS Sequoia caused by the Python.org installer, and macOS stub behaviour at `/usr/bin/python3`
- **Feature additions**: Error reporting, timestamped output to Downloads, and the interactive HTML report format were all developed through natural language conversation with Claude

The entire codebase — Python scanner, bash launcher, HTML/CSS/JS report generator, and readme — was written by Claude based on requirements specified in conversation.
(Not entirely true. I did write a sentence in the readme and now this makes 3 sentences what I wrote.)

---

## Licence

MIT — see [LICENSE](LICENSE) for details.
