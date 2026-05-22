# EMBLOCS Architecture

## 1. Overview

EMBLOCS is a real-time control system framework targeted at microcontrollers
(MCUs). It is inspired by block diagram tools used in control system design,
and uses a hardware analogy throughout: blocks are like integrated circuits,
pins are like IC pins, and signals are like the nets or wires on a schematic.

EMBLOCS provides a CMake-based build system for managing block variants and
generated artifacts, but does not impose a build structure on the project
author's own code. It runs on bare-metal MCUs and MCUs running an RTOS. It
is not intended for larger systems such as PCs or embedded Linux.

Currently supported targets:
- STM32G431 (ARM Cortex-M4), built with CMake and arm-none-eabi-gcc
- Raspberry Pi Pico / RP2040 (ARM Cortex-M0+), built with CMake and the Pico SDK

Planned targets:
- STM32F103 ("blue pill")
- FreeRTOS variants of the above

---

## 2. Core Abstractions

### 2.1 Blocks

A block is a reusable functional unit, analogous to an integrated circuit.
Examples include PID controllers, summers, integrators, filters, ADC inputs,
and PWM outputs. Blocks are the unit of reuse in EMBLOCS.

Each block:
- Exports one or more **pins** for inputs and outputs
- Exports one or more **functions** that implement its behavior
- Depends only on the core library, not on other blocks

Users may write custom blocks for specific projects. A custom block can often
replace a complex arrangement of simpler generic blocks with less overhead.

### 2.2 Pins

Pins are typed, directional ports on a block, analogous to pins on an
integrated circuit. Each pin has a type and a direction (`in` or `out`).

Pin types: `bool`, `u32`, `s32`, `float`, and `raw`. The `raw` type is
compatible with any signal type and is used for blocks that operate on
values without interpreting them (e.g., a signal passthrough).

A pin always points to a signal. When a pin is not connected to a
user-visible signal, it points to a private **dummy signal** internal to the
block instance. Dummy signals preserve the pin's last value and prevent null
pointer dereferences. Setting a pin's value with `=` writes into its dummy
signal; this is only permitted while the pin is unconnected.

### 2.3 Signals

Signals are named values that connect pins, analogous to nets or wires on a
schematic. Signal types mirror pin types: `bool`, `u32`, `s32`, and `float`.

When a signal is created, it is assigned a default value of `false` (bool),
`0` (u32 and s32), or `0.0` (float). Subsequent `=` subcommands can change
the value, but without an explicit `=` the value is still well defined.

Connectivity rules:
- A signal may drive any number of `in` pins.
- A signal may be driven by **at most one** `out` pin.
- A signal with no `out` pin driver may instead hold a value set directly
  with `=`.

Writing a value to a signal that already has an `out` pin driver is an error;
the policy governing this check is compile-time configurable.

### 2.4 Threads

Threads are periodic execution contexts. Each thread has a period (in
nanoseconds) and an ordered list of block functions to call. On bare-metal
systems, threads run in interrupt service routines (ISRs). On RTOS systems,
threads run as OS threads.

---

## 3. Namespaces

EMBLOCS maintains two distinct namespaces.

The **system-wide namespace** contains all block definitions, block instances,
signals, and threads. All names within this namespace must be unique; a block
instance, a signal, and a thread cannot share a name.

Each **block instance** has its own private namespace containing that
instance's pins and functions. Pins and functions share the same namespace
within a block instance and are addressed using qualified names of the form
`<blockname>.<pinname>` or `<blockname>.<funcname>`.

---

## 4. The System Definition Language

EMBLOCS systems are described using a scripting language. System descriptions
use the `.blocs` file extension. (A related language for describing individual
block templates uses the `.bloc` extension; see `bloc_language.md`.) The full
lexical and syntactic specification of the `.blocs` language is in
`blocs_language.md`; this section describes the language's structure and role.

### 4.1 Command Structure

Every command in the `.blocs` language follows a common pattern: the first
token identifies the object being defined or modified, and the remainder of
the line provides arguments, options, or subcommands that describe or act on
that object. This applies uniformly across all command types.

### 4.2 Command Categories

#### 4.2.1 Block Definition (`blockdef`)

Registers a block type from a `.bloc` template file, making it available for
instantiation. Options and parameters are passed to the `.bloc` toolchain.

    blockdef <type-name> <path-to-.bloc> [option...]

Block definitions are immutable once created. All block definitions needed by
a system must appear before any block instances that use them.

Block variants — parameterized forms of a block type — are also declared here.
Rather than maintaining separate source files for each variant, a single
`.bloc` file serves as a template, and parameters (such as the number of
channels or inputs) are supplied in the `blockdef` command to generate the
variant-specific C code.

Example — defining a 3-channel 2-to-1 multiplexor variant:

    blockdef mux_3ch_2to1 mux.bloc NUM_CHAN=3 NUM_INPUT=2

The resulting block type has pins: `ch00_in0`, `ch00_in1`, `ch01_in0`,
`ch01_in1`, `ch02_in0`, `ch02_in1`, `ch00_out`, `ch01_out`, `ch02_out`,
`select`. When `select=1`, each `chN_in1` is copied to `chN_out`.

#### 4.2.2 Block Instantiation (`block`)

Creates a named instance of a previously defined block type.

    block <instance-name> <type-name>

The instance inherits all pins and functions defined by its block type.

#### 4.2.3 Signal Commands (`signal`)

Creates a named signal of a given type, with a well-defined default value,
and optional initial value assignment and pin connections.

    signal <sig-name> <type> [subcommand...]

#### 4.2.4 Thread Commands (`thread`)

Creates a named thread with a given period and an optional initial list of
block functions in execution order.

    thread <thread-name> <period-ns> [+<blockname>.<funcname>...]

#### 4.2.5 Modification Commands

Existing objects are modified by naming them on the command line followed by
subcommands. This applies to signals, threads, and individual pins and
functions:

    <sig-name> [subcommand...]
    <thread-name> [subcommand...]
    <blockname>.<pinname> [subcommand...]
    <blockname>.<funcname> [subcommand...]

### 4.3 Subcommands

After an object is either created or identified, the remainder of the logical
line is a sequence of subcommands which act on the target object. Placing
multiple subcommands on one line is a notational convenience; logically each
subcommand is an independent operation on the same object. Subcommands execute
left-to-right. If a subcommand fails, it and all subsequent subcommands on the
line are abandoned; subcommands that already completed are not rolled back.

| Subcommand | Meaning |
|------------|---------|
| `=value`   | Set the value of a signal or unconnected pin |
| `+target`  | Connect: link a pin to a signal, add a function to a thread, or vice versa |
| `-target`  | Disconnect: unlink a named pin or function from this object |
| `-`        | Disconnect: unlink this pin or function from whatever it is connected to |
| `-+target` | Rebind: disconnect current target, then connect to new target |

When a pin is disconnected, its current value is preserved by copying it into
the pin's dummy signal.

### 4.4 Error Handling

Errors in `.blocs` commands never produce partial state changes within a
single subcommand. A subcommand either completes fully or leaves the system
state unchanged. Error categories include: name resolution failures, type
mismatches, direction or driver violations, and illegal value writes.

---

## 5. Deployment Modes

EMBLOCS supports a spectrum of deployment configurations controlled by
compile-time options in `emblocs_config.h`. The same `.blocs` file produces
all deployment modes; only the build configuration changes.

### 5.1 Dynamic (development)

- All modules compiled in, including the parser and name metadata
- System is configured at runtime by sending `.blocs` commands over UART
- Most flexible, largest flash and RAM footprint
- Use case: early development, interactive exploration

### 5.2 Static with Metadata (integration/debug)

- System pre-configured at startup via generated `system.c`
- Parser and name metadata still compiled in
- Runtime monitor can inspect and modify the running system by name
- Use case: integration testing, debug builds

### 5.3 Static, No Metadata (production)

- System pre-configured at startup via generated `system.c`
- Name strings stripped to minimize flash and RAM usage
- Functional behavior identical to the debug build
- Runtime monitor has limited or no visibility
- Use case: production firmware

---

## 6. Source Structure

### 6.1 `emblocs/src/emblocs/`

The core library. Key files:

| File | Role | Visibility |
|------|------|------------|
| `emblocs_config.h` | Project-specific configuration | Public — must be copied to project and edited |
| `emblocs_common.h` | Shared data structures | Public — included by API and component headers |
| `emblocs_api.h` | Core API declarations | Public — used by applications and blocks |
| `emblocs_comp.h` | Block-authoring API | Semi-public — used when writing blocks |
| `emblocs_priv.h` | Internal data structures | Private — only included by `.c` files |
| `emblocs_core.c` | Engine implementation | Compiled |
| `emblocs_show.c` | Display and inspection functions | Compiled; optionally stripped in production |
| `emblocs_parse.c` | `.blocs` language parser/interpreter | Compiled; optionally stripped in production |

Include hierarchy:

    emblocs_config.h
        ^
    emblocs_common.h
        ^           ^
    emblocs_api.h   emblocs_comp.h
             ^      ^
              emblocs_priv.h
                   ^
        emblocs_core.c  emblocs_show.c  emblocs_parse.c

`emblocs_config.h` is project-supplied and controls:
- Memory pool sizes
- Whether disconnect and remove operations are enabled
- Whether null pointer checks are compiled in
- Whether the parser and show modules are included

### 6.2 `emblocs/src/components/`

Generic block implementations. Each block depends only on the core library.
Blocks are designed to be independently testable via CI test harnesses.

### 6.3 `emblocs/src/misc/`

Utility code used by the core library:
- Linked list management
- Lightweight printf replacement
- Lightweight string parsing (string to float, string to integer, etc.)
- Serial port library implementing a combined human-readable stream and
  binary packet protocol

### 6.4 `emblocs/python/`

Build-time and runtime Python tools (see Section 7).

---

## 7. Python Tooling

### 7.1 Shared Object Model (`emblocs.py`)

All Python tools import `emblocs.py`, which defines the complete EMBLOCS
object model as Python classes. This single source of truth covers both
block-level objects (Block, Pin, Function, Parameter) and system-level
objects (Signal, Thread, BlockInstance).

By sharing the object model across tools, consistency is guaranteed: Tool 1,
Tool 2, and the runtime monitor all work with the same class hierarchy.

Parsers for the .bloc and .blocs languages are implemented as modules;
any tool that needs to parse a file imports the appropriate parser and
gets the object level model directly.

### 7.2 Runtime Monitor

A GUI tool (using Tkinter) that connects to a running EMBLOCS system over
UART. It imports `emblocs.py` and uses the same object model as the build
tools. Features:
- **Inspector**: list signals, show signal connections, show thread contents
- **Meters**: display signal values numerically at update rates limited by
  UART and GUI performance
- **Oscilloscope**: display signal values vs. time, capturing one sample per
  thread execution

### 7.3 Build-time Tools

EMBLOCS uses a two-tool model for block and system compilation. The tools
have distinct responsibilities and run at different times.

#### 7.3.1 Tool 1: Block Compiler (`bloc_compiler.py`)

Tool 1 is the single authority on block structure and pin layout. It operates
in two modes.

**Template mode** — run by the block author when creating or updating a
`.bloc` file. Produces:

- **`<block>.h`** — a header containing the instance struct definition and
  default parameter defines, using `BL_` preprocessor symbols for all
  variant-controlled values. Default values (from the `.bloc` file's
  `default=` clauses) are wrapped in `#ifndef`/`#endif` guards so that
  variant-specific values take precedence at build time while providing
  clangd with a complete compilation environment during editing. This file
  lives alongside `<block>.bloc` and `<block>.c` in the block's library
  and is checked into source control.
- **`<block>.c`** — a one-time source template with function stubs and a
  comment inventory of available pins. Generated only if the file does not
  already exist; the block author owns this file from the moment of creation
  and Tool 1 never overwrites it. The author may delete it to obtain a fresh
  template after significant structural changes.

Template mode may be run any number of times. Re-running after `.bloc`
changes is normal and safe: `<block>.h` is always regenerated, `<block>.c`
is left untouched if it exists. If the block author adds or renames a pin,
they must manually reconcile their `<block>.c` implementation with the
updated `<block>.h`. Tool 1 applies stable-output detection — `<block>.h`
is written to disk only if its content has changed, so unchanged files do
not receive updated timestamps and do not trigger unnecessary recompilation.

**Variant mode** — invoked by Tool 2 per `blockdef` command. Produces three
files in the project build directory:

- **`<variant>.h`** — a fully expanded variant-specific header with all
  `BL_` symbols replaced by concrete values and all names mangled with the
  block type name. Contains no preprocessor conditionals and no `BL_`
  symbols; safe for inclusion by `system.c` alongside headers for other
  variants.
- **`<variant>.c`** — a fully expanded variant-specific source file.
  Includes `<variant>.h` instead of `<block>.h`. All `BL_` symbols are
  replaced by concrete values and all `BL_MANGLE()` calls are expanded to
  their mangled forms. Conditional `#if`/`#endif` blocks are retained with
  literal values substituted, so the C preprocessor handles branch
  elimination normally. A `#line` directive at the top of the file points
  back to `<block>.c`, ensuring that compiler error messages refer to the
  file the author actually edits. (If the `#line` directive causes toolchain
  issues, the fallback is to document that `<variant>.c` line numbers
  correspond directly to `<block>.c` line numbers since no lines are added
  or removed during substitution.)
- **`<variant>.json`** — a full serialization of the block's object model,
  including all pins with their complete attribute sets (name, field name,
  type, direction, byte offset, array dimensions, metadata description) and
  all functions with their mangled symbol names. The schema is versioned.
  Consumed by Tool 2 when processing signal connections and pin references
  in the `.blocs` file.

All three variant-mode output files use stable-output detection. Tool 1
writes them only if their content has changed, so edits to the wiring region
of `system.blocs` do not trigger unnecessary recompilation of variant object
files.

The block author may use a standard C editor with full LSP support (clangd)
on `<block>.c`, because it includes `<block>.h` which provides default
parameter values. Clangd sees a complete, consistent compilation environment
without requiring a variant build to have been run first.

#### 7.3.2 Tool 2: System Compiler (`blocs_compiler.py`)

Tool 2 uses `blocs_parser.py` to read a `.blocs` system definition file
and build a complete in-memory model of the system using the classes
from `emblocs.py`.
For each `blockdef` command it invokes `bloc_parser.py` to parse the .bloc
file, then `bloc_resolver.py` to generate the specific variant.
For each `signal` and `thread` command it constructs the corresponding objects,
tracking connections, values, and thread ordering. The resulting in-memory
model is fully inspectable and is used to drive all output generation.

Tool 2 produces:

- **`system.cmake`** — CMake compile rules. For each `blockdef` command,
  emits an `add_library(... OBJECT ...)` rule that compiles `<variant>.c`
  to `<variant>.o`. No `-D` flags are needed since all substitutions are
  already performed in `<variant>.c`.
- **`system.c`** — instance struct declarations and signal initializers
  for static deployment modes.

#### 7.3.3 Build Dependency and Over-triggering

Tool 2 (and Tool 1 in variant mode) are triggered when `system.blocs`
changes. However, `system.blocs` has two regions with different change
frequencies: the structural region (`blockdef`/`block` commands, rarely
changed) and the wiring region (signal connections and value assignments,
changed frequently during tuning). Edits to the wiring region unnecessarily
re-trigger Tool 1 variant mode even though no structural change occurred.

The preferred mitigation is stable-output detection: Tool 1 in variant mode
generates its output content and writes to disk only if the content differs
from the existing files. If the files are unchanged, their timestamps are not
updated and CMake does not retrigger downstream C compilation. This is a
standard code-generation technique requiring minimal implementation effort.

### 7.4 Block Authoring Workflow

The intended workflow for creating or updating a block:

1. Author writes or updates `<block>.bloc` describing pins, parameters,
   private variables, and function names.
2. Author runs Tool 1 in template mode, which generates or updates
   `<block>.h` and generates `<block>.c` if it does not already exist.
   Re-running after `.bloc` changes is normal and safe. If structural
   changes are large enough that a fresh template is preferable, the author
   may delete `<block>.c` before re-running.
3. Author implements or updates the function bodies in `<block>.c`. The
   editor provides full C language support via clangd because the file is
   pure C with a complete header. If pins were added or renamed, the author
   must manually reconcile the implementation with the updated `<block>.h`.
4. When the system is assembled, Tool 2 reads the `.blocs` file, invokes
   Tool 1 in variant mode for each `blockdef` command, and generates
   variant-specific artifacts.

### 7.5 Name Mangling

When the same `.bloc` file is compiled for multiple variants (e.g., a
1-channel mux and a 3-channel mux), each variant's object file must
export distinct C symbols. All exported names — struct typedefs and
function names — are mangled using the block type name from the
`blockdef` command.

The block type name is passed as the preprocessor symbol `BL_BLOCK_NAME`.
A `BL_MANGLE(name)` macro in the generated header expands to
`<blocktype>_<name>`. For example, `BL_MANGLE(update)` in a compilation
for block type `mux2to1` expands to `mux2to1_update`.

In `<variant>.c`, Tool 1 performs this expansion directly during source
generation, so the compiled file contains fully mangled names and requires
no `-D` flags at compile time.

---

## 8. Build System

### 8.1 Philosophy

EMBLOCS uses CMake as its build system. All source is compiled per-project
into a project-specific build directory. There are no pre-compiled libraries;
all files are compiled with project-specific flags, allowing target-specific
optimizations even in library code. The linker discards unused code.

The core library — the `.c` and `.h` files in `emblocs/src/emblocs/` — is
compilable with any standard C toolchain. CMake is required for the variant
generation machinery, not for using the compiled library itself.

`emblocs_config.h` is project-supplied and never part of the library itself.
Only open-source toolchains are supported (`arm-none-eabi-gcc`, etc.).
Proprietary compilers are explicitly not supported.

### 8.2 File Locations

Files fall into two categories based on who owns them and where they live.

**Library source files** — live alongside the `.bloc` file in the block's
library directory, checked into source control:

| File | Owner | Notes |
|------|-------|-------|
| `<block>.bloc` | Block author | Hand-written |
| `<block>.c` | Block author | Hand-written after initial generation |
| `<block>.h` | Tool 1 | Generated; never hand-edited; checked in to support editor tooling without requiring a build |

The presence of `<block>.h` in source control is a deliberate exception to
the "generated files go in build/" rule, justified by the requirement that a
fresh checkout provides a working editor environment. CI should verify that
the checked-in `<block>.h` matches what Tool 1 would generate from the
current `<block>.bloc`.

**Project build artifacts** — live in the project build directory, not
checked into source control:

| File | Producer |
|------|----------|
| `<variant>.h` | Tool 1, variant mode |
| `<variant>.c` | Tool 1, variant mode |
| `<variant>.json` | Tool 1, variant mode |
| `<variant>.o` | C compiler |
| `system.c` | Tool 2 |
| `system.cmake` | Tool 2 |
| `system.o` | C compiler |

### 8.3 CMake Integration

The master `CMakeLists.txt` is hand-written and stable. It includes the
generated `system.cmake`:

```cmake
include(${CMAKE_BINARY_DIR}/system.cmake)
```

The generated `system.cmake` contains one `add_library(... OBJECT ...)` rule
per variant, compiling the generated `<variant>.c` directly:

```cmake
add_library(mux2to1 OBJECT ${CMAKE_BINARY_DIR}/mux2to1.c)
```

No `-D` flags are required since all substitutions are already present in
`<variant>.c`. The master `CMakeLists.txt` links the resulting object
libraries into the final firmware target.

---

## 9. Portability

EMBLOCS targets MCUs only — not PCs or embedded Linux. Supported and planned
compiler toolchains:

| Toolchain | Targets |
|-----------|---------|
| `arm-none-eabi-gcc` | STM32 (all variants), RP2040, Teensy 4.1 |
| `xtensa-esp32-elf-gcc` | ESP32 |
| `riscv32-esp-elf-gcc` | ESP32-C3/C6 |

Platform-specific code (GPIO, UART, timers) uses the platform's native SDK
directly. EMBLOCS does not define its own hardware abstraction layer — that
is the responsibility of the platform SDK. EMBLOCS abstracts the control
system layer (blocks, signals, threads), not the hardware layer.