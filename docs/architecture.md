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
- ESP32
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
systems, threads typically run in interrupt service routines (ISRs). On
RTOS systems, threads run as OS threads.  However, the core EMBLOCS system
does not directly control how threads are invoked.

By convention, a thread named `init` can be used for things that only need
to run once at startup; a program's main() function can simply invoke the
`init` thread once.  This is simply a convention, neither `init` functions
nor an `init` thread get special treatment by the toolchain.

---

## 3. Namespaces

EMBLOCS maintains three distinct namespaces.

The **block spec namespace** contains the names of all block templates that
have been loaded. A block spec name is derived from the base name of its
`.bloc` file. Block spec names do not conflict with names in the other
namespaces.

The **system-wide namespace** contains all block definitions, block instances,
signals, and threads. All names within this namespace must be unique; no two
items (block definition, block instance, signal, thread) can share a name.

Each **block instance** has its own private namespace containing that
instance's pins and functions. Pins and functions share the same namespace
within a block instance and are addressed using qualified names of the form
`<blockname>.<pinname>` or `<blockname>.<funcname>`.

---

## 4. The System Definition Language

EMBLOCS systems are described using a scripting language. System descriptions
use the `.blocs` file extension.  The full lexical and syntactic specification
of the `.blocs` language is in `blocs_language.md`; this section describes the
language's basic structure and role.

### 4.1 Command Structure

Every command in the `.blocs` language follows a common pattern: the first
token identifies the object being defined or modified, and the remainder of
the line provides arguments, options, or subcommands that describe or act on
that object. This applies uniformly across all command types.

### 4.2 Command Categories

#### 4.2.1 Block Definition (`blockdef`)

Registers a block type, making it available for instantiation. The first
argument is the name of the new block definition; the second is the name
of a block spec — the base name of a `.bloc` template file located via
the block search path. Optional `PARAM=value` pairs generate parameterized
variants from a single template.

    blockdef <def-name> <spec-name> [PARAM=value...]

Example — defining a 3-channel 2-to-1 multiplexor variant:

    blockdef mux_3ch_2to1 mux NUM_CHAN=3 NUM_INPUT=2

The resulting block type has pins: `ch00_in0`, `ch00_in1`, `ch01_in0`,
`ch01_in1`, `ch02_in0`, `ch02_in1`, `ch00_out`, `ch01_out`, `ch02_out`,
`select`. When `select=1`, each `chN_in1` is copied to `chN_out`.

See `blocs_language.md` Section 5.1 for full details including variant
creation and the block search path.

#### 4.2.2 Block Instantiation (`block`)

Creates a named instance of a previously defined block definition.

    block <instance-name> <def-name>

The instance inherits all pins and functions defined by its block definition.

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
| `+name`    | Connect: link a pin to a signal, add a function to a thread, or vice versa |
| `-name`    | Disconnect: unlink a named pin or function from target object |
| `-`        | Disconnect: unlink this pin or function from whatever it is connected to |
| `-+name`   | Rebind: disconnect current target, then connect to new target |

When a pin is disconnected, its current value is preserved by copying it into
the pin's dummy signal.

### 4.4 Error Handling

Errors in `.blocs` commands never produce partial state changes within a
single subcommand. A subcommand either completes fully or leaves the system
state unchanged. Error categories include: name resolution failures, type
mismatches, direction or driver violations, and illegal value writes.

---
## 5. The Block Definition Language

EMBLOCS control blocks consist of a mixture of generated and hand-written code.
The `.bloc` block definition language is used to describe the interfaces of a
given block.  Block instance data structures are generated automatically from
the `.bloc` file, then the block author writes code to implement the block
functionality.  The full lexical and syntactic specification of the `.bloc`
language is in `bloc_language.md`; this section describes the language's
basic features, structure and role; some statements such as `include` and
`var` are omitted here.

### 5.1 Block Statement

A `.bloc` file must begin with exactly one `block` statement, which defines
the name of the block and provides a description of its purpose and behavior.
The block name must match the base name of the `.bloc` file; a mismatch is
an error.

### 5.2 Parameter Statement

A `.bloc` file can contain zero or more `param` statements, each of which defines
a parameter than can be used to generate multiple variants from a single `.bloc`
file.  Parameters are named (by convention in UPPERCASE), and can be boolean or
unsigned integters.  All parameters must have a default value, and u32 parameters
can have optional minimum and maximum values.

### 5.3 Body Statements

The body section of a `.bloc` file follows the `block` and `param` (if any)
statements, and is what actually defines the block.  The body consists of
any combination of `pin` and `function` statements, which may be contained
in `#if <condition> / #endif` blocks.  The `<condition>` field of an `#if`
statement must be an expression containing only constants, operators, and/or
parameter names.

#### 5.3.1 Pin Statement

A `pin` statement defines one or more EMBLOCS pins.  Each statement starts with
the `pin` keyword, followed by the pin type and direction.  This is followed by
a pin name specification and an optional conditional.
Pins can be scalar or arrays.  A scalar pin is simple; it defines a single pin,
and the name specification is simply the pin name itself.  Array pins have
dimensions, and the name specification serves as a template to create unique
EMBLOCS pin names for each array element.  Array dimensions must be expressions
containing constants, operators, and/or parameter names.
Each pin can be followed by an optional `if` expression that determines if that
particular pin is exported; this allows sparse export from array pins.  The `if`
expression can include constants, operators, parameter names, and array index
names.


---
## 6. Deployment Modes

***Work in progress***
*at the moment only static deployment with no metadata (section 6.3) is supported*

EMBLOCS supports a spectrum of deployment configurations controlled by
compile-time options in `emblocs_config.h`. The same `.blocs` file produces
all deployment modes; only the build configuration changes.

### 6.1 Dynamic (development)

- All modules compiled in, including the parser and name metadata
- System is configured at runtime by sending `.blocs` commands over UART
- Most flexible, largest flash and RAM footprint
- Use case: early development, interactive exploration

### 6.2 Static with Metadata (integration/debug)

- System pre-configured at startup via generated `system.c`
- Parser and name metadata still compiled in
- Runtime monitor can inspect and modify the running system by name
- Use case: integration testing, debug builds

### 6.3 Static, No Metadata (production)

- System pre-configured at startup via generated `system.c`
- Name strings stripped to minimize flash and RAM usage
- Functional behavior identical to the debug build
- Runtime monitor has limited or no visibility
- Use case: production firmware

---

## 7. Source Structure

***This section is very likely to change***
*At the moment, none of the C code below is used; only the code types
defined in emblocs_common.h are used.  This will change when metadata
and runtime support are added.*

### 7.1 `emblocs/src/emblocs/`

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

### 7.2 `emblocs/src/components/`

Generic block implementations. Each block depends only on the core library.
Blocks are designed to be independently testable via CI test harnesses.

### 7.3 `emblocs/src/misc/`

Utility code used by the core library:
- Linked list management
- Lightweight printf replacement
- Lightweight string parsing (string to float, string to integer, etc.)
- Serial port library implementing a combined human-readable stream and
  binary packet protocol

### 7.4 `emblocs/python/`

Build-time and runtime Python tools (see Section 8).

---

## 8. Python Tooling

### 8.1 Shared Object Model (`emblocs.py`)

All Python tools import `emblocs.py`, which defines the complete EMBLOCS
object model as Python classes. This single source of truth covers block
spec objects (BlockSpec, ParamSpec, PinSpec, DimSpec, FunctSpec,
Statement), block definition objects (BlockDef, FieldDef, PinDef, FunctDef),
system level objects (BlockInstance, PinInstance, FunctInstance, Signal, Thread),
and finally the overall Design object that fully defines a system.

By sharing the object model across tools, consistency is guaranteed: the
.bloc compiler, the .blocs compiler, and the runtime monitor all work
with the same class hierarchy.

Parsers for the .bloc and .blocs languages are implemented as modules;
any tool that needs to parse a file imports the appropriate parser and
gets the object level model directly.

### 8.2 Runtime Monitor

***Under Construction***

A GUI tool (using Tkinter) that connects to a running EMBLOCS system over
UART. It imports `emblocs.py` and uses the same object model as the build
tools. Features:
- **Inspector**: list signals, show signal connections, show thread contents
- **Meters**: display signal values numerically at update rates limited by
  UART and GUI performance
- **Oscilloscope**: display signal values vs. time, capturing one sample per
  thread execution

### 8.3 Block Compiler (`bloc_compiler.py`)

The block compiler and the .bloc language are used by block authors to
define individual control blocks.

#### 8.3.1 Blocks and Variants

Many control blocks have a fixed configuration; always the same input and
output pins, always the same functions that perform the same tasks.  A system
can contain multiple instances of the block, but each instance is the same.

However, sometimes a block naturally tends to have variations.  A classic
example is a multiplexor that chooses one of several inputs to be copied
to an output.  A multiplexor might choose one of two inputs, or one of
three, or one of ten.  It might also be convenient to have a multiplexor
with multiple parallel channels, such that one `select` input switches all
channels in parallel.  EMBLOCS supports this with the concept of `variants`.

A single `.bloc` file can support multiple variants by means of `parameters`.
For example, the `mux` (multiplexor) example has parameters called `NUM_CHAN`
for the number of parallel channels, and `NUM_INPUT` to determine if it
selects one of two, one of three, etc. inputs.  Each unique combination of
parameter values produces a unique variant, but all share the same `.bloc`
file and source code.

To manage variants, EMBLOCS has two concepts, `BlockSpec` or block specification,
and `BlockDef`, or block definition.  A `BlockDef` describes exactly one
variant; it is fully resolved and can be used to create block instances in
a system design.  A `BlockSpec` is derived from a `.bloc` file and cannot
itself be used to create block instances; instead the `BlockSpec` must be
resolved to a `BlockDef` first.

If a `.bloc` file does not contain parameters, the resulting `BlockSpec`
can produce only one `BlockDef`.  However, a `.bloc` file with parameters
results in a `BlockSpec` with parameters, which can be used to create
multiple different `BlockDefs` by supplying different parameter values.
Each `BlockDef` describes a different variant.

#### 8.3.2 Block Authoring Workflow

The intended workflow for creating or updating a block:

1. Author writes or updates `<block>.bloc` describing parameters, pins,
   private variables, and function names.
2. Author runs `bloc_compiler.py` on `<block>.bloc`, which generates
   `<block>.h` and `<block>.c`, which are referred to as `template` files.
   These files are created in the same directory as `<block>.bloc` and
   should be placed under version control.
3. `<block>.h` contains a typedef for the instance data structure, which
   may have conditional fields and/or variable size arrays based on
   parameter values.  `<block>.c` contains empty bodies for the functions
   defined by the `.bloc` file, and includes `<block>.h` to define the
   instance data structure.
4. Author implements the function bodies by editing `<block>.c`. The
   editor provides full C language support via clangd because the file
   is pure C with a complete header.
5. If changes to the block specification are needed, the `.bloc` file
   can be edited, and `bloc_compiler.py` run again.  It will update
   `<block>.h` which is always a generated file, but it will not overwrite
   `<block>.c`, since that file might contain function implementations
   added by the block author.  For a complete fresh start, the author
   can delete `<block>.c`, in which case the block compiler will generate
   both files.
6. The `<block>.h` and `<block>.c` files are normally never compiled into
   actual code for the system.  Instead, each `blockdef` command in the
   system is process by the system compiler `blocs_compiler.py`, producing
   `<variant>.h` and `<variant>.c` in the system build directory.  These
   variant files have fixed fields and fixed size arrays as defined by
   the specific block definition, and are the code that is actually
   compiled and linked into the finished system.

#### 8.4 System Compiler (`blocs_compiler.py`)

The system compiler `blocs_compiler.py` reads a `.blocs` system definition
file and builds a complete in-memory model of the system using the classes
from `emblocs.py`.  For each `blockdef` command, it invokes `bloc_parser.py`
to parse the .bloc file, then `bloc_resolver.py` to generate the specific
`<variant>.h` and `<variant>.c` files in the system build directory.  For
each `signal` and `thread` command it constructs the corresponding objects,
tracking connections, values, and thread ordering. The resulting in-memory
model is fully inspectable and is used to drive all output generation.

In addition to the variant source files, the system compiler also produces
the following files in the system build directory:

- **`<system>.cmake`** — CMake compile rules. For each `blockdef` command,
  emits an `add_library(... OBJECT ...)` rule that compiles `<variant>.c`
  to `<variant>.o`.
- **`<system>.c`** — instance struct declarations and signal initializers
  for static deployment modes.

#### 8.4.1 Build Dependency and Over-triggering

`blocs_compiler.py` is triggered when `<system>.blocs` changes. However,
`<system>.blocs` has two regions with different change frequencies: the
structural region (`blockdef`/`block` commands, rarely changed) and the
wiring region (signal connections and value assignments, changed frequently
during tuning). The system compiler checks for existing variant source
files, and only re-writes those files if their content has changed.  This
prevents unnecessary re-compilation when no structural change has occurred.


### 8.5 Name Mangling

When the same `.bloc` file is compiled for multiple variants (e.g., a
1-channel mux and a 3-channel mux), each variant's object file must
export distinct C symbols. All exported names — struct typedefs and
function names — are mangled using the block type name from the
`blockdef` command.

The block type name is passed as the preprocessor symbol `BL_BLOCK_NAME`.
A `BL_MANGLE(name)` macro in the generated header expands to
`<blocktype>_<name>`. For example, `BL_MANGLE(update)` in a compilation
for block type `mux2to1` expands to `mux2to1_update`.  This allows the
`update` functions for multiple multiplexor variants to coexist in the
linker namespace.

---

## 9. Build System

### 9.1 Philosophy

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

### 9.2 File Locations

Files fall into two categories based on who owns them and where they live.

**Library source files** — live alongside the `.bloc` file in the block's
library directory, checked into source control:

| File | Owner | Notes |
|------|-------|-------|
| `<block>.bloc` | Block author | Hand-written |
| `<block>.c` | Block author | Hand-written after initial generation |
| `<block>.h` | bloc_compiler | Generated; never hand-edited; checked in to support editor tooling without requiring a build |

The presence of `<block>.h` in source control is a deliberate exception to
the "generated files go in build/" rule, justified by the requirement that a
fresh checkout provides a working editor environment. CI should verify that
the checked-in `<block>.h` matches what bloc_compiler.py would generate from
the current `<block>.bloc`.

**Project build artifacts** — live in the project build directory, not
checked into source control:

| File | Producer |
|------|----------|
| `<variant>.h` | blocs_compiler |
| `<variant>.c` | blocs_compiler |
| `<variant>.o` | C compiler |
| `<system>.c` | blocs_compiler |
| `<system>.cmake` | blocs_compiler |
| `<system>.o` | C compiler |

### 9.3 CMake Integration

The master `CMakeLists.txt` is hand-written and stable. It includes the
generated `<system>.cmake`:

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

## 10. Portability

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
