# EMBLOCS Runtime Monitor — Startup and Configuration Design

This document captures design decisions made during the development of the
runtime monitor. It covers project identity, startup flow, and configuration
file architecture. Protocol design and data model extensions are documented
in `monitor.md`.

Although this document uses words like "does" and "are", the design is far
from frozen, and everything in here should be considered a starting point
rather than a cast-in-stone decision.  Some things are pretty stable, others
are very fluid.

---

## 1. Project Identity

A "project" for the runtime monitor is anchored to a specific **target
system**, not to a `.blocs` file or a directory on disk. The target is the
authoritative source of its own identity.

The target stores two items that identify the project:

- The **base name** of the `.blocs` file used to build it (e.g. `blink`)
- A **hash** of the `.blocs` file content

These are stored as C string constants in the firmware, transmitted to the
monitor during the connect sequence, and used to locate matching local files
on the PC.

The target also stores, for each BlockSpec:

- The BlockSpec **name** (derived from the `.bloc` filename)
- A **hash** of the `.bloc` file content
- A **compressed representation** of the `.bloc` file (minus descriptions,
  comments, includes, and vars) for use when local files are not available

BlockSpecs are stored as an array of structs:

```c
typedef struct {
    const char *name;
    const char *hash;
    const char *compressed;
} blockspec_t;

const blockspec_t blockspecs[] = {
    { "simple", "abc123", "compressed representation" },
    { "", "", "" }   // sentinel
};
```

---

## 2. Local File Enrichment

The monitor builds a `Design` object from target metadata. Local files are
optional enrichment — they are never required for basic operation.

When local `.bloc` files are available and their hashes match the target's
stored hashes, they are used to add descriptions and other metadata not
stored in compressed form on the target.

The monitor might never read a `.blocs` file.  This is still fluid.  If the
porject contains a `.blocs` file, that file has useful information that is
not stored in the target itself, including things like paths to `.bloc` files
(as `search` commands).  If a `.blocs` file is available, and especially if
the hash matches, we may choose to build a "reference" Design object from
the `.blocs` file before building the "live" Design object using target data.

The debugger analogy is useful here: a debugger works minimally with just
the target (memory reads, register inspection), and gains progressively more
capability as local files are provided (symbol names, source-level debugging).
The monitor follows the same pattern:

- **Minimum:** connect to target, read/write memory, display pin and signal
  names from target metadata
- **Enhanced:** local `.bloc` files found and hashes match — add descriptions
- **Full:** (future) additional local context for topology visualization etc.

---

## 3. Configuration File Architecture

Two distinct config files serve different purposes and have different scopes.

### 3.1. User-Level Recents File

One file per user per machine, stored in a user-specific location
(e.g. `~/.emblocs/recents.json` on Linux,
`%APPDATA%\emblocs\recents.json` on Windows).

Contains only a list of recent projects, each with:

```json
{
    "recent_projects": [
        {
            "name": "blink",
            "hash": "abc123def456",
            "project_path": "/home/user/projects/blink/blink.json",
            "last_connected": "2026-06-18T22:30:00"
        }
    ]
}
```

The recents file serves as a (name, hash) → project path lookup table.
When the monitor connects to a target and receives the project name and hash,
it checks the recents file first. A match immediately identifies the project
session file without any filesystem search or user interaction.

The recents file is updated on every successful connect.  Most likely
we will present the list in most-recently-used-first order.

### 3.2. Project Session File

One file per project, named `<projectname>.json`, stored alongside
`<projectname>.blocs` in the project directory.

Contains everything specific to one project/target combination:

- Serial port name and baud rate
- Window geometry
- Custom bloc search paths (for local `.bloc` file enrichment)
- Any other per-project UI state

Written on exit, read after the project is identified at startup.

### 3.3. Installation Template

A template config file ships with the EMBLOCS installation at
`$EMBLOCS/emblocs_cfg.json`. It provides built-in defaults for all known
config keys. Tools load this first, then overlay project session data.

---

## 4. Startup Flow

### 4.1. Two-Phase GUI Startup

The monitor uses a two-phase startup to avoid Tkinter's requirement that
the full application be built before any window appears, while still needing
config data (window geometry, port settings) to build the main application.

**Phase 1 — Startup applet:**
A small, simple window with minimal config needs. Shows:
- List of recent projects (from recents file)
- "Open project..." button (file browser)
- "New project..." button (specify directory)

The applet stores the user's choice and calls `root.quit()`. The main
program checks the result:
- If the user closed the window → `sys.exit(0)`
- If the user made a choice → destroy the applet window, proceed to phase 2

Tkinter supports this pattern: create a `Tk()` instance, run `mainloop()`,
call `destroy()`, then create a new `Tk()` instance for the main app.

**Phase 2 — Main application:**
Built with full knowledge of the selected project. Loads the project session
file, creates all widgets with correct initial values, starts the main
event loop.

### 4.2. Startup Cases

**Case 1 — Explicit project on command line:**
```
emblocs_monitor blink.blocs
```
or
```
emblocs_monitor blink.json
```
Project is unambiguous. Load `blink.json`, skip the startup applet entirely,
go directly to phase 2.

**Case 2 — Command line, no arguments, one `.blocs` file in cwd:**
Search recents for an entry matching the current working directory. If
exactly one match, use it. If multiple or none, fall through to the startup
applet.

**Case 3 — Command line, no arguments, ambiguous or no local project:**
Show startup applet. User selects from recents list or browses for a
project file.

**Case 4 — Invoked from icon:**
Working directory is unlikely to be a project directory. Show startup
applet unconditionally.

### 4.3. Connect-Time Project Resolution

The startup applet normally decides what project to use (or gets that
information from the user) before starting the main application, and
only the main application connects to the target.  The main application
can usually connect automatically because the last used port and baud
rate are stored in the project config.

A possible extension might be for the startup applet to offer a "connect"
option.  If selected, the startup applet would prompt for a port and baud
rate and begin the connection.

After connecting to a target, the monitor receives the project name and hash.
Resolution proceeds in order:

1. Check recents file for matching (name, hash) entry → offer to go to
   that project (which implies that directory)
2. Search current working directory for `<name>.blocs` and verify hash →
   offer to use that project.
3. Offer to search the entire disk for a matching .blocs file - only if we
   can search efficiently. 
4. If not found, offer to create a new project (and get location from user)

---

## 5. Open Questions

- Exact location of the user-level recents file (platform-specific paths)
- Whether the startup applet should offer a "connect first, find project
  later" option for targets that have never been seen before
- How the monitor handles the case where the recents file points to a
  project path that no longer exists
