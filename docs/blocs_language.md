# EMBLOCS `.blocs` Language Reference

This document is the complete language reference for `.blocs` system definition
files. It covers lexical rules, command syntax, subcommand semantics, and error
handling in enough detail to implement a parser and interpreter.

For the architectural role of the `.blocs` language within EMBLOCS — how it
relates to blocks, signals, threads, deployment modes, and the build system —
see `ARCHITECTURE.md`.

For the `.bloc` language used to define individual block templates, see
`bloc_language.md`.

---

## 1. Input Model

- Input is **ASCII-only**. Any non-ASCII byte is a lexical error.
- Permitted control characters are: space (0x20), tab (0x09), line feed (0x0A),
  and carriage return (0x0D). All other control characters are errors.
- CRLF (0x0D 0x0A) and bare LF (0x0A) are both accepted as line endings.
- Commands are **line-oriented**: a logical line forms one complete command.
- Before tokenization, two line-level transformations are applied in order:
  1. **Line continuation**: a backslash (`\`) as the last non-whitespace
     character on a physical line causes it to be joined with the next
     physical line. The backslash and the line ending are consumed; they
     do not appear in the resulting logical line. Whitespace between the
     backslash and the line ending is not permitted.
  2. **Comment stripping**: a `#` character and everything following it
     on the physical line are discarded. A backslash inside a comment has
     no continuation meaning.
- After these transformations, the remaining content is split into tokens
  by whitespace.
- **Line numbers** in error messages always refer to physical lines.

---

## 2. Lexical Elements

### 2.1 Identifiers

An identifier is a name given to a block definition, block instance, signal,
thread, pin, or function.

- Permitted characters: `[A-Za-z_][A-Za-z0-9_]*`
- Maximum length: **31 characters** (a practical limit for readability; GCC
  imposes no significant identifier length constraint for the supported targets)
- Case-sensitive: `MySignal` and `mysignal` are distinct names

### 2.2 Full Names

A full name refers to a pin or function within a specific block instance:

    <block-instance-name>.<pin-or-func-name>

Both parts are identifiers subject to the rules in 2.1. The dot separator is
not whitespace-separated from the identifiers on either side.

### 2.3 Tokens

After line continuation and comment stripping (see Section 1), the remaining
content is split into tokens by whitespace (spaces and tabs). No quoting
mechanism and no escape sequences are supported within tokens. The following
characters have special meaning as token-initial characters:

| Character | Role |
|-----------|------|
| `=`       | Value assignment subcommand |
| `+`       | Connect/add subcommand |
| `-`       | Disconnect/remove subcommand (named or unnamed) |
| `-+`      | Rebind subcommand (disconnect then connect) |

### 2.4 Values

Values are used with the `=` subcommand to set the contents of a signal or
unconnected pin. The stored representation depends on the signal or pin type:

| Signal/pin type | Stored representation |
|-----------------|-----------------------|
| `bool`          | Integer 0 or 1 only; any non-zero value normalizes to 1 |
| `u32`           | Unsigned 32-bit integer in range [0, 2³²−1] |
| `s32`           | Signed 32-bit integer in range [−2³¹, 2³¹−1] |
| `float`         | 32-bit IEEE 754 floating-point |

Values are supplied in the `.blocs` language as expressions. Integer
expressions support decimal and hexadecimal literals (e.g. `42`, `0xFF`),
arithmetic and bitwise operators (e.g. `48*200`, `MASK&0xF`), and the
keywords `true` and `false` (for bool targets only). Float expressions
support decimal floating-point with optional exponent (e.g. `1.5`, `1.5e-3`,
`25.4/4`). Expression syntax and operator precedence follow the rules of
`expressions.py`; because values are single tokens, expressions must be
written without internal whitespace. Out-of-range results are errors.

### 2.5 Period Values

The thread period is specified in nanoseconds as an integer expression,
following the same rules as integer value expressions in Section 2.4.
The result must be a positive integer in the range [1, 2³²−1].
Common forms include decimal literals (`1000000`), hexadecimal (`0xF4240`),
and arithmetic expressions (`1000*1000`).

### 2.6 Paths

Paths in `blockdef` commands always use forward slashes as directory
separators, following POSIX conventions, regardless of the host operating
system. Both absolute and relative paths are supported. Relative paths are
interpreted relative to the location of the `.blocs` file, not the current
working directory of the tool invocation. The Python toolchain converts paths
to native separators internally when opening files.

---

## 3. Namespaces

### 3.1 System-wide Namespace

The following object types share a single flat namespace:

- Block definitions (declared with `blockdef`)
- Block instances (declared with `block`)
- Signals (declared with `signal`)
- Threads (declared with `thread`)

All names in this namespace must be unique. Declaring any object with a name
already in use is an error, regardless of object type.

### 3.2 Block-instance Namespace

Each block instance has a private namespace containing its pins and functions.
Pins and functions share this namespace, so a pin and a function within the
same block instance cannot have the same name.

Members of a block-instance namespace are addressed using qualified names:

    <block-instance-name>.<pin-or-func-name>

The block-instance namespace is populated automatically when the `block`
command creates the instance. It is defined by the block's type and cannot
be modified directly by `.blocs` commands.

---

## 4. Types

### 4.1 Signal Types

Signals carry one of four 32-bit atomic types:

| Type    | Description |
|---------|-------------|
| `bool`  | Boolean (also spelled `bit` — keyword TBD) |
| `u32`   | Unsigned 32-bit integer |
| `s32`   | Signed 32-bit integer |
| `float` | 32-bit IEEE 754 floating-point |

All signal types are 32 bits wide, which allows atomic read/write on all
supported MCU architectures without requiring additional synchronization.

### 4.2 Pin Types

Pins use the same four types as signals, plus one additional type:

| Type    | Compatible signal types |
|---------|------------------------|
| `bool`  | `bool` |
| `u32`   | `u32` |
| `s32`   | `s32` |
| `float` | `float` |
| `raw`   | Any — the pin reads or writes the 32-bit value without type interpretation |

Type compatibility is checked at connection time. Connecting a pin to a
signal of an incompatible type is an error.

---

## 5. Commands

All commands follow a common structure: the first token identifies the object
being defined or modified; the remaining tokens are arguments, options, or
subcommands that act on that object.

Commands fall into four categories by creation keyword (`blockdef`, `block`,
`signal`, `thread`), plus modification forms that name an existing object
directly. A first token that is a qualified name (`block.pin` or
`block.function`) unambiguously identifies a pin or function modification
command.

### 5.1 Block Definition Creation

    blockdef <type-name> <path> [option...]

Registers a block type, making it available for instantiation. `<type-name>`
is an identifier placed in the system-wide namespace. `<path>` is the path
to the `.bloc` template file (see Section 2.6 for path conventions). Options
are `NAME=value` pairs passed to the block compiler; they supply variant
parameters controlling code generation.

Block definitions are immutable once created. All `blockdef` commands for
types needed by a system must appear before any `block` commands that
instantiate those types.

#### 5.1.1 Block Variant Creation

A block variant is a parameterized form of a block type. Rather than
maintaining separate source files for each variant, a single `.bloc` file
serves as a template and parameters are supplied as options on the `blockdef`
command. The toolchain generates the variant-specific C source from the
template and the supplied parameters.

Example — registering a 3-channel 2-to-1 multiplexor variant:

    blockdef mux_3ch_2to1 components/mux.bloc NCHANNELS=3 NINPUTS=2

### 5.2 Block Instantiation

    block <instance-name> <type-name>

Creates a named instance of a previously defined block type. `<instance-name>`
is placed in the system-wide namespace. The instance inherits all pins and
functions from `<type-name>`. The block type must have been declared with
`blockdef` before this command is processed.

Example:

    block pid1 pid_controller

### 5.3 Signal Creation

    signal <sig-name> <type> [subcommand...]

Creates a named signal of the given type and places it in the system-wide
namespace. A newly created signal is assigned a default value: `false` for
`bool`, `0` for `u32` and `s32`, and `0.0` for `float`. Zero or more
subcommands may follow on the same logical line; they are executed in order
after the signal is created. See Section 6 for subcommand details.

Example — creating a float signal, setting an initial value, and connecting
it to two pins:

    signal velocity float =0.0 +encoder.output +pid1.feedback

### 5.4 Thread Creation

    thread <thread-name> <period-ns> [subcommand...]

Creates a named thread with the given period (in nanoseconds) and places it
in the system-wide namespace. Zero or more subcommands may follow on the same
logical line; they are executed in order after the thread is created. See
Section 6 for subcommand details.

Example — a 1 kHz thread running two functions in order:

    thread fast_loop 1000000 +pid1.compute +pwm_out.update

### 5.5 Modification Commands

Existing objects are modified by naming them as the first token, followed by
subcommands. Four forms are supported.

#### 5.5.1 Signal Modification

    <sig-name> [subcommand...]

Permitted subcommands: `=value`, `+block.pin`, `-block.pin`, `-+block.pin`

#### 5.5.2 Thread Modification

    <thread-name> [subcommand...]

Permitted subcommands: `+block.func`, `-block.func`, `-+block.func`

#### 5.5.3 Pin Modification

    <blockname>.<pinname> [subcommand...]

Permitted subcommands: `=value`, `+sig-name`, `-`, `-+sig-name`

#### 5.5.4 Function Modification

    <blockname>.<funcname> [subcommand...]

Permitted subcommands: `+thread-name`, `-`, `-+thread-name`

---

## 6. Subcommands

After an object is either created or identified, the remainder of the logical
line is a sequence of subcommands which act on the **target object** — the
object named or created at the start of the command. Placing multiple
subcommands on one line is a notational convenience; logically each subcommand
is an independent operation on the same target object. Subcommands execute
strictly left-to-right.

Where a subcommand takes an argument, that argument is the **named object**:
the object whose name follows the `+`, `-`, or `-+` operator.

### 6.1 Execution Model

Each subcommand is validated before any mutation is applied. If validation
of a subcommand fails, that subcommand and all subsequent subcommands on the
same logical line are abandoned. State changes made by earlier subcommands on
the same line are not rolled back — they stand as if each had been issued on
its own line.

### 6.2 Value Assignment (`=`)

    =<value>

Sets the value of the target object.

- For a **signal**: sets the signal's stored value. Writing to a signal that
  has an `out` pin driver is an error; this check is policy-controlled at
  compile time via `emblocs_config.h`.
- For a **pin**: only permitted when the pin is currently unconnected (pointing
  to its dummy signal). Writes the value into the dummy signal.

### 6.3 Connect (`+`)

    +<n>

Connects the named object to the target object. Using `+` on a pin or
function that is already connected is an error; use `-+` (Section 6.5) to
move an existing connection intentionally.

| Target | Named Object | Effect |
|--------|-------------|--------|
| Signal | `block.pin` | Connect the named pin to the target signal |
| Pin | `sig-name` | Connect the target pin to the named signal |
| Thread | `block.func` | Append the named function to the target thread's execution list |
| Function | `thread-name` | Append the target function to the named thread's execution list |

Type and direction compatibility are checked before a pin-signal connection
is made. A signal may connect to any number of `in` pins. A signal may
connect to at most one `out` pin; connecting a second `out` pin is an error.

### 6.4 Disconnect (`-`)

    -<n>
    -

Two forms are available. The **named form** (`-<n>`) disconnects the named
object from the target object and is an error if the named object is not
currently connected to the target. The **unnamed form** (`-`) disconnects the
target object from whatever it is currently connected to; if the target is
already unconnected, this is a no-op.

| Target | Named Object | Effect |
|--------|-------------|--------|
| Signal | `block.pin` | Disconnect the named pin from the target signal; error if not connected |
| Pin | (none) | Disconnect the target pin from its current signal; no-op if unconnected |
| Thread | `block.func` | Remove the named function from the target thread; error if not present |
| Function | (none) | Remove the target function from any thread; no-op if not in any thread |

When a pin is disconnected, its current value is preserved: the value is
copied into the pin's dummy signal before the connection is severed.

### 6.5 Rebind (`-+`)

    -+<n>

Disconnects the target object from its current connection (if any) and
connects it to the named object. If the target is currently unconnected,
the disconnect portion is a no-op and the connect proceeds normally. If the
connect portion fails for any reason (type mismatch, driver conflict, etc.),
the overall subcommand fails and the target is left unconnected.

For functions, `-+` always appends the function to the end of the named
thread's execution list, regardless of where the function previously appeared.
This makes it straightforward to move a function to the end of its current
thread or to transfer it to a different thread entirely.

| Target | Named Object | Effect |
|--------|-------------|--------|
| Signal | `block.pin` | Disconnect named pin from its current signal; connect to target signal |
| Pin | `sig-name` | Disconnect target pin from its current signal; connect to named signal |
| Thread | `block.func` | Disconnect named function from its current thread; append to target thread |
| Function | `thread-name` | Disconnect target function from its current thread; append to named thread |

Rebind is symmetric: the user may express a reconnection from whichever
object is more convenient to name first.

---

## 7. Ordering and Dependencies

Within a `.blocs` file, commands are processed strictly in order with no
read-ahead. The following ordering rules apply:

### 7.1 Required Ordering

- A `blockdef` command must appear before any `block` command that references
  its type name.
- A `block` command must appear before any signal, thread, pin, or function
  modification command that references any of its pins or functions.
- A `signal` command must appear before any modification command that
  references it by name.
- A `thread` command must appear before any modification command that
  references it by name.

Violations of these rules manifest as name resolution errors (see Section
8.2): the parser encounters an unknown name and rejects the command
immediately, without read-ahead to determine whether the name will be defined
later.

### 7.2 Dynamic Mode

In dynamic (runtime) mode, where commands arrive over UART, each command is
validated against the current state of the system at the time it is received.
A command that references an object not yet defined is rejected with a name
resolution error; the user may then issue the prerequisite commands and retry.
This behavior is identical to file parsing.

---

## 8. Error Handling

### 8.1 Error Atomicity

Each subcommand is atomic: it either completes fully or leaves the system
state unchanged. If a subcommand fails, all subsequent subcommands on the
same logical line are skipped. Subcommands that already completed on the
same line are not rolled back (see Section 6.1).

### 8.2 Error Categories

| Category | Examples |
|----------|---------|
| Lexical errors | Non-ASCII input, illegal control character, malformed token |
| Name resolution errors | Unknown identifier, name already in use, wrong namespace, object referenced before it is defined |
| Type errors | Pin-signal type mismatch, value out of range for type |
| Direction/driver errors | Connecting a second `out` pin to a signal, using `+` on an already-connected pin or function |
| Illegal write errors | Writing `=value` to a signal with an `out` driver, writing `=value` to a connected pin |

### 8.3 Error Reporting

Errors are reported with the physical line number of the failing command. In
dynamic (UART) mode, error messages are returned over the same UART stream.
In static (compile-time or startup) mode, errors are reported via the
build-time toolchain or the startup serial log, depending on the deployment
configuration.

---

## 9. Grammar Summary (EBNF)

The following grammar is a normative summary. Lowercase names are
non-terminals; quoted strings and character class patterns are terminals.
Optional elements are enclosed in `[...]`; repetition is indicated by `{...}`.

```
file            ::= { logical-line }

logical-line    ::= physical-line { '\' newline physical-line } newline

physical-line   ::= [ command ] [ '#' comment-text ]

command         ::= blockdef-cmd
                  | block-cmd
                  | signal-cmd
                  | thread-cmd
                  | signal-mod-cmd
                  | thread-mod-cmd
                  | pin-mod-cmd
                  | func-mod-cmd

blockdef-cmd    ::= 'blockdef' identifier path { param }
param           ::= identifier '=' expression

block-cmd       ::= 'block' identifier identifier

signal-cmd      ::= 'signal' identifier type { signal-subcmd }
type            ::= 'bool' | 'bit' | 'u32' | 's32' | 'float'
                                                       (* 'bool'/'bit' TBD *)

thread-cmd      ::= 'thread' identifier period-ns { thread-subcmd }
period-ns       ::= expression

signal-mod-cmd  ::= identifier { signal-subcmd }
signal-subcmd   ::= '=' expression
                  | '+' fullname
                  | '-' fullname
                  | '-+' fullname

thread-mod-cmd  ::= identifier { thread-subcmd }
thread-subcmd   ::= '+' fullname
                  | '-' fullname
                  | '-+' fullname

pin-mod-cmd     ::= fullname { pin-subcmd }
pin-subcmd      ::= '=' expression
                  | '+' identifier
                  | '-'
                  | '-+' identifier

func-mod-cmd    ::= fullname { func-subcmd }
func-subcmd     ::= '+' identifier
                  | '-'
                  | '-+' identifier

fullname        ::= identifier '.' identifier

identifier      ::= [A-Za-z_][A-Za-z0-9_]*            (* max 31 chars *)
expression      ::= token  (* integer or float expression; no internal whitespace *)
path            ::= token  (* see Section 2.6 for path conventions *)
token           ::= <any non-whitespace ASCII sequence>
```

**Open keyword:** The `bool`/`bit` type keyword is not yet finalized. The
grammar and semantics are identical regardless of which spelling is chosen.

---

## 10. Examples

### 10.1 Minimal System

A single PID controller reading an encoder and driving a PWM output, running
at 1 kHz.

```
# Block type registrations
blockdef pid_controller  pid.bloc
blockdef encoder_input   encoder.bloc
blockdef pwm_output      pwm.bloc

# Block instances
block enc   encoder_input
block pid   pid_controller
block pwm   pwm_output

# Signals
signal position  float  +enc.output  +pid.feedback
signal command   float  =0.0         +pid.setpoint
signal effort    float  +pid.output  +pwm.input

# Thread: 1 kHz control loop
thread fast 1000000 +enc.read +pid.compute +pwm.write
```

### 10.2 Signal Modification

Adjusting the command signal value and reconnecting a pin after the system
above has been defined:

```
# Change the setpoint value
command =1.5

# Move the effort signal connection from pwm.input to a different pin
effort -pwm.input -+pwm.input2
```

### 10.3 Line Continuation

A signal connection spread across multiple physical lines:

```
signal bus_voltage float   \
    =12.0                  \
    +monitor.v_in          \
    +protection.v_sense
```

### 10.4 Block Variant

Registering and using a parameterized multiplexor with one channel and
three inputs:

```
blockdef mux3 components/mux.bloc NCHANNELS=1 NINPUTS=3

block source_select mux3

signal ch0  float  +source_select.ch00_in0
signal ch1  float  +source_select.ch00_in1
signal ch2  float  +source_select.ch00_in2
signal sel  u32    +source_select.select
signal out  float  +source_select.ch00_out
```

### 10.5 Pin-side Rebind

Moving a pin's connection from one signal to another using the pin-side
rebind form:

```
# pid1.feedback is currently connected to position
# Move it to filtered_position instead
pid1.feedback -+filtered_position
```

This is equivalent to the signal-side form:

```
filtered_position +pid1.feedback
position -pid1.feedback
```

but expresses the intent more directly when the pin is the natural
starting point.

### 10.6 Function Rebind

Moving a function to the end of its thread after deciding the original
ordering was incorrect:

```
# enc.read is currently somewhere in fast_loop; move it to the end
fast_loop -+enc.read
```

Or equivalently, from the function side:

```
enc.read -+fast_loop
```