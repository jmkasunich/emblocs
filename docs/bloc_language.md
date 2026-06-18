# EMBLOCS `.bloc` Language Reference

This document is the complete language reference for `.bloc` block description
language. It covers the purpose and structure of `.bloc` files, the lexical
rules, command syntax, subcommand semantics, and error
handling in enough detail to implement a parser and interpreter.

For the architectural role of blocks within EMBLOCS — how blocks relate to
signals, threads, and the system definition language — see `ARCHITECTURE.md`.

For the `.blocs` system definition language used to instantiate blocks and
connect signals, see `blocs_language.md`.

**NOTE** Much of the information in sections 5, 7, and 9 of this document
is actually architecture rather than language defintion.  It will be moved
at some point in the future.

---

## 1. Overview and Design Goals

### 1.1 Purpose

A `.bloc` file is a template that describes a control block: the pins it
exports, the private data it maintains, and the functions it provides. It
serves two audiences simultaneously:

- The **block author** uses a `bloc_compiler.py` to read the `.bloc` file
  and generates a C header and a C source template.
- The **system designer** uses a system compiler `(blocs_compiler.py)` to
  assemble a system containing multiple blocks.  The system compiler reads
  `.bloc` files indirectly in response to `blockdef` commands in the
  `.blocs` system definition, and generates variant-specific headers, source
  files, and build rules.

### 1.2 Three-File Model

A block is defined by three files:

- `<block>.bloc` — the block template, written in the `.bloc` DSL
- `<block>.h` — the block instance data structure
- `<block>.c` — the block implementation

The `<block>.bloc` file describes the block interface at a high level.  It
is written by the block author and is used by multiple EMBLOCS tools.

The `<block>.h` file contains a typedef for the block instance data structure.
Each block instance has a copy of this structure, which contains block internal
state as well as the pin pointers that are used to interconect blocks into a
larger system.  The `<block>.h` file is created by running `bloc_compiler.py`
on `<block>.bloc` and is never edited manually.  It should be checked into
version control.

The `<block>.c` file contains the actual C implementation of the control block.
An initial template version is created by running `bloc_compiler.py` on
`<block>.bloc`, but that version contains only empty template functions.
The file is then edited by the block author to provide block implementation.

If it is neccessary to edit `<block>.bloc`, for example to add a pin or a
private variable, re-running the block compiler will regenerate `<block>.h`,
but the block author is responsible for updating `<block>.c`.  The block
compiler will never overwrite an existing `<block>.c` file because it might
contain implementation code that must not be lost.  If changes to a .bloc
file are extreme enough that the block author wants to start over with the
implementation, they can delete or rename `<block>.c` and rerun the bloc
compiler to generate a fresh template file.



### 1.3 Two-Tool Model

Tool 1 is the single authority on block structure and pin layout. It operates
in two modes.

**Tool 1** — run by the block author when creating or updating a `.bloc` file:

```
bloc_compiler.py mux.bloc
```

Produces:

- `<block>.h` — a header containing the instance struct definition,
  convenience macros, and default parameter defines. Default values (from
  the `.bloc` file's `default=` clauses) are provided using `#ifndef`/
  `#endif` guards so that variant-specific values take precedence at build
  time while providing clangd with a complete, squiggle-free compilation
  environment during editing. This file lives alongside `<block>.bloc` and
  `<block>.c` in the blocks library and is checked into source control.
- `<block>.c` — a one-time source template containing function stubs, the
  instance cast line, and an inventory of available pins as comments.
  Generated only if the file does not already exist; the block author owns
  it from the moment of creation and Tool 1 never overwrites it.

Template mode may be run any number of times. Re-running after `.bloc`
changes is normal and safe: `<block>.h` is always regenerated, `<block>.c`
is left untouched if it exists. If the block author adds or renames a pin,
they must manually reconcile their implementation with the updated `<block>.h`.
If the structural changes are large enough that starting from a fresh template
is preferable, the author may delete `<block>.c` before re-running.

<details>
<summary> DEPRECATED SECTION - was "variant mode" for Tool 1 - click to view
</summary>

**Tool 1, variant mode** — invoked by Tool 2 per `blockdef` command:

```
bloc_compiler.py mux.bloc --mode=variant --name=mux2to1 --params="NCHANNELS=2 NINPUTS=3"
```

Produces three files in the project build directory:

- `<variant>.h` — a fully expanded variant-specific header with all `BL_`
  symbols replaced by concrete values and all names mangled with the block
  type name. Contains no preprocessor conditionals and no `BL_` symbols;
  safe for inclusion by `system.c` alongside headers for other variants.
- `<variant>.c` — a fully expanded variant-specific source file. Includes
  `<variant>.h` instead of `<block>.h`. All `BL_` symbols are replaced by
  concrete values and all `BL_MANGLE()` calls are expanded to their mangled
  forms by Tool 1 directly, without relying on the C preprocessor for these
  substitutions. Conditional `#if`/`#endif` blocks are retained with literal
  values substituted, so the C preprocessor handles branch elimination
  normally at compile time. A `#line` directive at the top of the file
  points back to `<block>.c`, so compiler error messages refer to the file
  the author actually edits rather than the generated file. (If the `#line`
  directive causes toolchain issues, the fallback is to document that
  `<variant>.c` line numbers correspond directly to `<block>.c` line numbers
  since no lines are added or removed during substitution.) The block
  author's own `#define`s, `#ifdef`s for target-specific code, and other
  preprocessor usage pass through untouched into `<variant>.c` and are
  handled by the C preprocessor normally at compile time. Tool 1 only
  substitutes the specific `BL_` symbols it defined; it does not reimplement
  the C preprocessor in general.
- `<variant>.json` — a full serialization of the block's object model,
  including all pins with their complete attribute sets (EMBLOCS-visible
  name, C struct field name, type, direction, byte offset in the instance
  struct, array dimensions, and metadata description) and all functions with
  their EMBLOCS-visible names and mangled C symbol names. The schema is
  versioned. This file is the authoritative interface between Tool 1 and
  Tool 2; Tool 2 never parses `.bloc` files directly.

All three variant-mode output files use stable-output detection: Tool 1
writes them only if their content has changed, avoiding unnecessary
recompilation when only the wiring region of `system.blocs` changes.

</details>

**Tool 2: The system compiler** reads a `.blocs` system definition file and
builds a complete in-memory model of the system using the shared object model
from `emblocs.py`. For each `blockdef` command it invokes Tool 1 in variant
mode to obtain the variant artifacts, then deserializes `<variant>.json` into
the object model. For each `signal` and `thread` command it constructs the
corresponding objects, tracking connections, values, and thread ordering.
The in-memory model is fully inspectable and drives all output generation.
Tool 2 produces:

- `system.cmake` — CMake compile rules. For each `blockdef` command, emits
  an `add_library(... OBJECT ...)` rule that compiles `<variant>.c` to
  `<variant>.o`. No `-D` flags are required since all substitutions are
  already performed in `<variant>.c`.
- `system.c` — instance struct declarations and signal initializers for
  static deployment modes.

### 1.4 Shared Object Model

All Python tools — the block compiler, the system compiler, and the
runtime monitor — import `emblocs.py`, which defines the complete
EMBLOCS object model as Python classes. Block-level classes (Block,
Pin, Function, Parameter) and system-level classes (Signal, Thread,
BlockInstance) are all defined here.

### 1.5 Relationship to Variants

A single `.bloc` file may describe a family of related blocks parameterized
by compile-time values supplied by the `blockdef` command in a `.blocs` file.
Each distinct set of parameter values produces a **variant** — a block type
with its own name, its own struct definition, and its own compiled object file.

The `.bloc` file uses `param` declarations to describe what parameters it
accepts, their types, valid ranges, and defaults. The block compiler validates
parameter values at `blockdef` time and reports errors before any C
compilation occurs.

---

## 2. Lexical Rules

### 2.1 Input Model

- Input is **ASCII-only**. Any non-ASCII byte is a lexical error.
- Line endings are bare LF (0x0A) or CRLF (0x0D 0x0A).
- A statement is the basic unit of the .bloc language.
- A statement consists of one or more whitespace separated tokens, which
must be on one physical line.
- The tokens of a statement may optionally be followed by a comment or a
description; see section 2.2 for details.
- Statements that introduce a named object (such as block, pin, param,
var, and function) are called declarations. Control flow statements (#if,
#endif) are statements but not declarations.

### 2.2 Comments and Descriptions

Two forms of documentation are supported, descriptions and comments.

- Descriptions are read by the parser, are associated with individual
statements, and can be made available to various tools as documentation.
The syntax of descriptions supports multiple lines and control over whitespace.
- Comments exist only for the benefit of a human reading or writing a .bloc
file; they are discarded by the parser.

Descriptions start with `///`.  A description applies to a specific statement,
and the starting `///` must appear after (but on the same line as) the tokens
of the statement.

Once started, a description can extend over multiple lines by repeating
the `///` marker on each line.  All characters (including whitespace, slash,
and newline) after the `///` marker are part of the description.  A multi-line
description ends when the parser encounters a line whose first non-whitespace
content is not `///`.

Comments start with `//` and extend to the end of the physical line.  A comment
may appear on a line by itself, or it may appear after the tokens of a statement.

Block-style comments (`/* */`) are not supported. The `#` character is
reserved for preprocessor-style directives (`#if`, `#endif`) and must not
be used as a comment character.

### 2.3 Identifiers

Identifiers follow C rules: `[A-Za-z_][A-Za-z0-9_]*`. A practical maximum
length of 31 characters is recommended for readability; this is consistent
with the identifier limit in `blocs_language.md`. Pin names that will be
visible in the `.blocs` system definition language are subject to that
language's identifier rules.

### 2.4 Keywords

Reserved keywords: `block`, `param`, `include`, `pin`, `var`,
`function`, `if`, `#if`, `#endif`, `true`, `false`, `input`, `output`,
`bool`, `u32`, `s32`, `float`, `raw`, `default`, `min`, `max`.

### 2.5 Whitespace

Tokens are separated by spaces or tabs. Leading and trailing whitespace
around tokens is ignored. Blank lines are ignored.  Whitespace in descriptions
is preserved for formatting; see section 2.2 for details.

Tokens are atomic: no internal whitespace is permitted within a token.
This applies to array dimension specifiers (`fieldname[i=NCHAN]`), name
templates (`ch{i:2}_out`), and expressions (`(INPUTS>>i)&1`).

### 2.6 Expressions

Expressions may appear as the condition in `#if` directives, as array dimensions,
in `if` clauses on `pin` declarations, and in pin name templates. Because tokens
may not contain internal whitespace, expressions must be written without
spaces.  An expression can be a simple numeric constant, a variable name, or
an expression with multiple operands and operators.

**Operands:**
- Integer literals (decimal or hexadecimal with `0x` prefix)
- Parameter names (evaluate to the parameter's integer value)
- Index variables introduced by array dimension specifiers (see Section 3.3.3)

**Operators**:

| Operator | Meaning |
|----------|---------|
| `>>`, `<<` | Bitwise shift |
| `&` | Bitwise AND |
| `\|` | Bitwise OR |
| `^` | Bitwise XOR |
| `~` | Bitwise NOT (unary) |
| `+` | Addition |
| `-` | Subtraction |
| `*` | Multiplication |
| `/` | Division |
| `%` | Modulo |
| `-` | Negation (unary) |
| `==`, `!=` | Equality |
| `>`, `<` | Comparison |
| `>=`, `<=` | Comparison |
| `&&` | Logical AND |
| `\|\|` | Logical OR |
| `!` | Logical NOT (unary) |
| `( )` | Grouping |

Expressions use C-style operators such as && and ||, but the parser uses
Python operator precedence which differs from C in some cases.  Block
authors should use parentheses in expressions to make operator precedence
unambiguous.

---

## 3. Declaration Types

A .bloc file consists of three sections, in order: header, parameters, and
body.  The header contains exactly one `block` statement that describes
the block. The parameters section contains zero or more `param` declarations
which can be used to generate customized variants of the block, and may also
contain optional `include` statements that allow exteral files to be included
before a block instance data structure is defined. The body contains the rest
of the block definition: `pin`, `var`, and `function` declarations optionally
grouped within `#if`/`#endif` blocks.

The order in which `pin` and `var` declarations appear in the body determines
the order of fields in the generated C instance struct.  Block authors may
choose this ordering deliberately, for example to optimize cache usage.
For a description of the instance struct and its role in the EMBLOCS
framework, see `architecture.md`.

### 3.1 Block Declaration

    block <NAME> /// description
    
Declares the name of the block and describes the block's purpose and behavior.
Exactly one block statement must appear in a .bloc file.  While descriptions
are optional for some statements, a block statement must have one.  Block
descriptions should take advantage of the multi-line syntax:

    block limit1 /// Clamps input to [min, max] range.
                 ///   Both bounds are inclusive.

### 3.2 Parameter Declaration

    param <type> <NAME> default=<value> [min=<value>] [max=<value>]  /// descripton

Declares a variant parameter. Parameters values are supplied on the `blockdef`
command line in the `.blocs` system definition and are validated by the
.bloc compiler before any C compilation occurs.

- `<type>` is one of `bool` or `u32`.
- `<NAME>` is an identifier. By convention, parameter names are UPPERCASE,
  matching the `BL_<NAME>` preprocessor symbols they become in generated C
  code. For example, `param NCHANNELS` produces `BL_NCHANNELS`.
- `default=<value>` is required. It specifies the value used when the
  parameter is not supplied on the `blockdef` command line, and also the
  value provided in `<block>.h` under `#ifndef` guards for editor support.
- `min=<value>` and `max=<value>` are optional and apply only to `u32`
  parameters. The block compiler rejects parameter values outside this range.
- A `///` description should describe what the parameter controls
  structurally (e.g., "if true, export the enable pin"), not what the
  resulting pin does (that belongs on the `pin` declaration).
- A `//` comment may be used instead for notes that are not intended for
  tool consumption.

Examples:

    param bool HAS_ENABLE  default=0   /// if true, export the enable pin
    param u32  NCHANNELS   default=1  min=1  max=16  /// number of independent channels

### 3.3 Include Declaration

    include <NAME>  or  include "NAME"

Allows external files to be included in the C source before the instance
data block structure is declared.  This is necessary if any `var` declaration
uses a data type that is declared in a header as opposed to part of standard
C.  Multiple `include` statements are allowed, and the files will be included
in the order in which the `include` statements appear.  The token following
the `include` keyword will be copied verbatim into the source file(s).

### 3.4 Pin Declaration

    pin <type> <direction> <name-spec> [if <expr>]  /// description

Declares a pin exported by the block. Pins appear in the generated instance
struct as pointers to the appropriate signal type.

The `#if`/`#endif` construct and the trailing `if` clause are both mechanisms
for conditionality, but they control different things and serve different
purposes:

- **`#if`/`#endif`** controls **struct allocation**: whether the field exists
  in the generated C struct at all. If the enclosing `#if` condition is false,
  no struct member is emitted, no memory is allocated, and no C code may
  reference that field name.
- **Trailing `if <expr>`** controls **EMBLOCS visibility**: whether a pin
  slot (or array slot) is exported as an EMBLOCS pin visible to the system
  developer. A field may exist in the struct while some or all of its slots
  are not exported, in which case those slots are initialized to `NULL` in
  `system.c` and must not be dereferenced at runtime.

For scalar pins, allocating without exporting is wasteful; the `#if`/`#endif`
form is the natural choice. For array pins, the two mechanisms compose
naturally: the outer `#if` gates whether the array exists at all, and the
trailing `if` gates which slots within it are exported.

#### 3.4.1 Pin Type

One of: `bool`, `u32`, `s32`, `float`, `raw`.

The `raw` type is compatible with any signal type and is used for blocks that
operate on values without interpreting them (e.g., a multiplexor).

In generated C code, pin fields use the corresponding typedef from
`emblocs_comp.h`: `bl_pin_bit_t`, `bl_pin_u32_t`, `bl_pin_s32_t`,
`nl_pin_float_t`, `bl_pin_raw_t`.

#### 3.4.2 Pin Direction

One of: `input`, `output`.

#### 3.4.3 Name and Dimensions

The third token in a `pin` declaration specifies the pin's EMBLOCS-visible
name and optional array dimensions. This token is written without internal
whitespace; dimension specifiers are attached directly to the name. The C
struct field name is derived automatically from this token and is not
specified by the block author.

##### 3.4.3.1 Name Template

The name portion of the token is a string that becomes the EMBLOCS-visible
pin name for scalar pins, or a template for generating indexed pin names for
array pins. It may contain one or more format specifiers of the form:

    {expr:N}

where `expr` is an expression (see Section 2.6) that may reference
parameters and index variables (see Section 3.3.3.2) in scope, and
`N` is a single digit from 1 to 9 specifying the minimum number of
digits, zero-padded.

Array pins must have at least one format specifier; without one, all
array members would share the same EMBLOCS pin name, which is an error.
Scalar pins never require format specifiers, but may use them if the
block author wishes.

The C struct field name is derived from the name template by replacing
each `{expr:N}` specifier with `N` zeros and appending `_`. For example:

| Template | Field name |
|----------|------------|
| `in` | `in_` |
| `ch{i:2}_out` | `ch00_out_` |
| `ch{i:2}_in{j:1}` | `ch00_in0_` |

The derived field name must be a valid C identifier. The parser validates
this and reports an error if the template produces an invalid result.

The derived field name is used for namespace collision detection at parse
time. All pins, vars, and functions in a block share one namespace; duplicate
derived field names are an error.

##### 3.4.3.2 Array Dimensions

Array dimensions are appended directly to the name template, one per dimension,
using the form:

    [varname=size]

where `varname` is a name chosen by the block author for the index
variable of that dimension, and `size` is an expression (see Section 2.6)
that evaluates to a positive integer giving the array size. The index
variable takes integer values from 0 to `size`-1, one value per array
slot, and is used to generate unique pin names for each slot and to
control which slots are exported as pins. It is in scope for the name
template and the trailing export condition of the same pin declaration.
It must not collide with a parameter name or with another index variable
on the same pin.

| Form | Meaning |
|------|---------|
| `name` | Scalar — one pin |
| `name[i=PARAM]` | 1D array — `PARAM` pins, index variable `i` |
| `name[i=P1][j=P2]` | 2D array — `P1`×`P2` pins, index variables `i` and `j` |

A maximum of two dimensions is supported.

##### 3.4.3.3 Examples

```
// scalar pin, no template specifiers, no dimensions
// EMBLOCS name: "in",  field name: "in_"
pin float  input   in   /// value to be processed

// 1D array
// EMBLOCS names: ch00_out, ch01_out, ...  field name: ch00_out_
pin raw    output  ch{i:2}_out[i=NCHAN]   /// mux output

// 2D array, template uses both index variables
// EMBLOCS names: ch00_in0, ch00_in1, ch01_in0, ...  field name: ch00_in0_
pin raw    input   ch{i:2}_in{j:1}[i=NCHAN][j=NINPUT]   /// mux input
```

#### 3.4.4 Trailing Export Condition

    pin <type> <direction> <name-spec> if <expr>

The optional trailing `if <expr>` clause controls which pin slots are
exported as EMBLOCS pins. The expression is evaluated for each slot using
the current values of all parameters and in-scope index variables. Slots
for which the expression evaluates to zero (false) are not exported:
they receive no EMBLOCS-visible name, do not appear in the JSON metadata,
and are initialized to `NULL` in `system.c`.

The expression is a single token (no internal whitespace) evaluated using
the same expression language as `#if` directives (see Section 2.6).

For scalar pins, the trailing `if` clause makes the pin conditionally
exported while still allocating the struct field. This is useful only in
unusual cases; the `#if`/`#endif` form is generally preferable for scalar
pins since it avoids allocating a field that will never be used.

For array pins, the index variable iterates from 0 to `size`-1 and the
trailing `if` clause is evaluated independently for each array member,
enabling sparse export from a dense array. Unexported slots are set to
`NULL` and must be checked before dereferencing in the block's C
implementation.

##### 3.4.4.1 Examples

```
// 1D array with sparse export using a trailing if clause
// dimension is a constant (3), but could also be a parameter
// struct field is a 3-element array; elements 0 and 2 are exported, element 1 is not
// EMBLOCS names: "ch00_out", "ch02_out"  field name: "ch00_out_"
pin raw    output  ch{i:2}_out[i=3]  if i!=1   /// dont' export channel 1

// 1D array with bitmask-driven sparse export
// MASK parameter determines which elements are exported
// struct field is a 16-element array; exported elements depend on MASK value
// EMBLOCS names: e.g. "pin00_in", "pin03_in", ... for MASK=0x0009
// field name: "pin00_in_"
pin bool   input   pin{i:2}_in[i=16]  if (MASK>>i)&1   /// GPIO input pins
```

#### 3.4.5 Pin Description

A `///` annotation on a `pin` declaration should describe the pin's behavior
and semantics. This metadata is stored in the JSON output and may be
displayed by the runtime monitor as help text.

### 3.5 Private Variable Declaration

    var <C-declaration>;

Declares a private variable in the instance struct. Everything after the `var`
keyword up to and including the terminating semicolon is passed verbatim into
the generated struct definition. The block compiler does not parse or validate
the C declaration; it is the block author's responsibility to ensure it is
valid C.

Private variables may be of any C type, including arrays, pointers, and
structs. They are not visible to the `.blocs` system definition language and
do not appear in the EMBLOCS JSON metadata. Use `//` comments (not `///`) to
annotate `var` declarations.

EMBLOCS guarantees that all `var` fields are zero-initialized before any
block function is called, regardless of whether the instance is statically
or dynamically allocated. Block authors who need non-zero initial values
should set them on the first run of their block function(s).

Examples:

    var float error_integral;       // PID integrator state
    var uint16_t input_bitmask;     // runtime copy of INPUTS param
    var GPIO_TypeDef *base_addr;    // hardware register base address
    var float history[4];           // filter history buffer

`var` declarations may appear inside `#if`/`#endif` blocks if they are
conditionally needed.

### 3.6 Function Declaration

    function <name>  /// description

Declares a function exported by the block. The function name is chosen by
the block author; by convention, simple blocks use `update`. The function
prototype is fixed by the EMBLOCS framework:

    void <name>(void *instance_data, uint32_t periodns);

The block compiler uses function declarations to generate function stubs in
the `.c` template and to register functions in the block metadata stored in
`<variant>.json`.

In `<block>.h`, function names are mangled using the `BL_MANGLE` macro (see
Section 5.2) to ensure uniqueness when the same `.bloc` file is compiled for
multiple variants. In `<variant>.c`, Tool 1 performs this expansion directly
during source generation.

A `///` description annotation should briefly describe what the function does
and, for blocks with multiple functions, when it should be called relative to
other functions in a thread.

Examples:

    function update  /// clamp in to [min, max] and copy to out
    function read    /// read IDR and drive input pins; call early in thread
    function write   /// read output pins and drive ODR/BSRR; call late in thread

By convention, a function named `init` can be defined to do any one-time setup
that the block requires.  Also by convention, a .blocs file can declare a
thread named `init` and add all `init` functions to it; the main program would
then run that thread once at startup.  Note the the .bloc and .blocs languages
to not assign any special meaning to `init` functions or threads; this is simply
a useful pattern for block and system authors.

---

## 4. Conditional Constructs

### 4.1 Conditional Blocks

    #if <expression>
    ... statements ...
    #endif

Conditionally includes a block of statements. When resolving a `BlockSpec`
to a fully resolved `BlockDef`, the expression is evaluated against the
concrete parameter values. If the expression is true (non-zero), the enclosed
statements are included in the resolved block; otherwise they are excluded.
At parse time, all statements are processed regardless of the `#if` condition,
since parameter values are not yet known.

Because `#if` expressions are not evaluated at parse time, the parser cannot
determine that two `#if` blocks are mutually exclusive. Two declarations with
the same name in mutually exclusive `#if` blocks — such as `#if PARAM` and
`#if !PARAM` — will be incorrectly reported as a namespace collision even
though only one can ever be active. Block authors must use distinct names for
declarations in mutually exclusive `#if` blocks.

`#if`/`#endif` expressions may be nested.

The `#if` directive also appears verbatim in the generated `<block>.h`
surrounding the corresponding struct fields, using `BL_` preprocessor symbols,
so the C compiler sees the same conditional structure during compilation.

The expression must be a single token (no internal whitespace). See Section 2.6
for the expression language.

### 4.2 Choosing Between `#if`/`#endif` and Trailing `if`

The two conditionality mechanisms serve distinct purposes and are not
interchangeable:

| Mechanism | Controls | Use when |
|-----------|----------|----------|
| `#if`/`#endif` | Struct field allocation | Field should not exist if condition is false |
| Trailing `if` | EMBLOCS pin visibility | Field should exist, but only some slots are exported |

For most conditional scalar pins, `#if`/`#endif` is the right choice. For
array pins with bitmask-driven sparse export, the trailing `if` on the `pin`
statement is the right choice. The two may be combined: an outer `#if` gates
whether the array is allocated at all, and a trailing `if` gates which slots
within it are exported.

---

## 5. Generated Artifacts

### 5.1 Block Header (`<block>.h`)

Generated by Tool 1 in template mode. Contains:

- A "do not edit" comment identifying the source `.bloc` file
- Include guard
- `#include "emblocs_comp.h"`
- Default parameter defines, each guarded by `#ifndef`/`#endif` so that
  variant-specific values take precedence when compiling a variant while
  providing clangd with resolved symbols during editing:

```c
#ifndef BL_NCHANNELS
#define BL_NCHANNELS (1)
#endif
#ifndef BL_HAS_ENABLE
#define BL_HAS_ENABLE (0)
#endif
```

- Name mangling macros (see Section 5.2)
- The instance struct typedef, with `BL_PARAMNAME` symbols for all
  variant-controlled dimensions and `#if BL_PARAMNAME` / `#endif` guards
  for all conditional fields, in declaration order from the `.bloc` file
- A local typedef aliasing the mangled struct name to `self_t` for
  readability in `<block>.c`
- Convenience macros for each pin (see Section 5.4)

This file is included only by `<block>.c`. It lives alongside `<block>.bloc`
and `<block>.c` in the block's library and is checked into source control.

### 5.2 Name Mangling

When the same `.bloc` file is compiled for multiple variants, the resulting
object files must not have conflicting symbol names. All exported C symbols
(function names, struct typedefs) are mangled using the block type name
supplied by the system compiler.

The block type name is passed as the preprocessor symbol `BL_BLOCK_NAME`.
`<block>.h` defines mangling macros:

```c
#define BL_CONCAT(a, b)  a##b
#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)
```

The instance struct is typedef'd as `BL_MANGLE(t)`. For readability in
`<block>.c`, `<block>.h` immediately aliases this to `self_t`:

```c
typedef BL_MANGLE(t) self_t;
```

Function declarations in `<block>.c` use `BL_MANGLE`:

```c
void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    ...
}
```

In `<variant>.c`, Tool 1 performs all `BL_MANGLE()` expansions directly
during source generation, so no `BL_` symbols appear in the compiled file.

### 5.3 Variant-Specific Header (`<variant>.h`)

Generated by Tool 1 in variant mode for each `blockdef` command. Lives in
the project build directory. Contains:

- A comment identifying the source `.bloc` file and the parameter values
- Include guard
- `#include "emblocs_comp.h"`
- The fully expanded instance struct typedef with all `BL_` symbols replaced
  by their concrete values and all conditional fields either included or
  excluded based on parameter values
- The struct is typedef'd as `<variant>_t` (e.g., `mux2to1_t`)

This file contains no preprocessor conditionals and no `BL_` symbols. It
may be safely included by `system.c` alongside headers for other variants
of the same block without conflict.

### 5.4 Convenience Macros

`<block>.h` defines a convenience macro for each pin that expands to the
struct field access. For scalar pins, the macro includes the pointer
dereference:

```c
#define IN   (*self->in)
#define OUT  (*self->out)
```

For array pins, the macro expands to the array base without dereferencing,
leaving indexing and dereferencing to the caller:

```c
#define IN   (self->in)
#define OUT  (self->out)
```

**Note:** This inconsistency between scalar and array pin macros is a known
issue. A resolution is deferred pending a concrete proposal. Block authors
who find the inconsistency confusing may ignore the macros and access pins
directly through `self->fieldname`.

Convenience macro names may collide with macros defined by platform SDKs or
the C standard library. Block authors should be aware of this risk. Macro
naming conventions are an open issue; see Section 6.

Conditional pin macros are guarded by the same `#if BL_PARAMNAME` /
`#endif` that guards the struct field.

### 5.5 Source Template (`<block>.c`)

Generated by Tool 1 in template mode only if the file does not already
exist. Contains:

- `#include "<block>.h"`
- For each declared function: a stub using `BL_MANGLE`, the `self_t`
  cast line, a `(void)periodns` suppression line with a comment to delete
  it if `periodns` is used, and a comment inventory of available pins
  showing which are conditional

Example generated template for a block with `HAS_ENABLE` and `HAS_HOLD`
parameters:

```c
#include "integrator.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    // TODO: implement update
    // Pins available:
    //   IN, OUT  (always present)
#if BL_HAS_ENABLE
    //   ENABLE   (conditional on BL_HAS_ENABLE)
#endif
#if BL_HAS_HOLD
    //   HOLD     (conditional on BL_HAS_HOLD)
#endif
}
```

### 5.6 Variant Source (`<variant>.c`)

Generated by Tool 1 in variant mode. Lives in the project build directory.
Contains the full content of `<block>.c` with all `BL_` symbols replaced by
concrete values and all `BL_MANGLE()` calls expanded. The block author's
own preprocessor usage (`#define`, `#ifdef`, etc.) passes through untouched.

A `#line` directive at the top points back to `<block>.c`:

```c
#line 1 "integrator.c"
```

This causes compiler error messages to report file and line numbers from
`<block>.c` rather than `<variant>.c`, since the two files have identical
line numbers (no lines are added or removed during substitution).

The CMake rule for `<variant>.c` requires no `-D` flags:

```cmake
add_library(integrator_with_hold OBJECT ${CMAKE_BINARY_DIR}/integrator_with_hold.c)
```

### 5.7 JSON Metadata (`<variant>.json`)

** Currently not defined, and may be deleted **

Generated by Tool 1 in variant mode. Lives in the project build directory.
Contains a full serialization of the block's object model for consumption
by Tool 2. The schema is versioned. At minimum, the JSON represents:

- Block-level attributes: variant name, source `.bloc` file path, block
  description metadata, schema version
- For each pin: EMBLOCS-visible name, C struct field name, type, direction,
  byte offset in the instance struct, array dimensions, metadata description
- For each function: EMBLOCS-visible name, mangled C symbol name, metadata
  description
- For each parameter: name, type, concrete value for this variant, default
  value, min/max bounds if specified, metadata description

The full JSON schema is defined by the Python classes in `emblocs.py` and
is authoritative over this prose description.

---

## 6. Open Issues

The following design questions are unresolved. They are documented here to
avoid losing track of them and to provide context for future decisions.

### 6.1 Convenience Macro Consistency

For every pin field, two convenience macros are generated:

**Value macros** — evaluate to the signal value directly:

```c
FOO_          // scalar pin value
BAR_(i)       // 1D array element value at index i
BAZ_(i, j)    // 2D array element value at indices i, j
```

**Pointer macros** (`pNAME_`) — evaluate to the pointer or array base:

```c
 pFOO_         // address of scalar pin data
*pFOO_         // value of scalar pin data (same as FOO_)
 pBAR_         // base address of 1D array
 pBAR_[i]      // address of element i
*pBAR_[i]      // value of element i (same as BAR_(i))
 pBAZ_         // base address of 2D array
 pBAZ_[i][j]   // address of element [i][j]
*pBAZ_[i][j]   // value of element [i][j] (same as BAZ_(i, j))
```

Block authors should use the value macro for normal signal access and
the pointer macro only when pointer-level access is needed (NULL checks,
passing pin pointers to helper functions).

### 6.2 Pin Field Name Collision

Convenience macro names may collide with macros from platform SDKs or the
C standard library. We append an underscore to names when creating structure
fields and macros in an attempt to avoid collisions.  A more systematic
mitigation (e.g., a block-type prefix on all macros) is deferred.

### 6.3 Initialization of var fields

Structure fields created by the `var` statement are intialized to zero.
If non-zero values are needed, the block author must use one field as a
flag to force initialization the first time the main update function runs.

### 6.4 Bool/Bit Keyword

The `bool` pin and signal type may be renamed `bit` for consistency with
the `.blocs` language, where this keyword is also unresolved. The `.bloc`
language will follow whatever decision is made for `.blocs`.

### 6.5 Function Calls in Expressions

The expression language supports arithmetic operators but not function
calls. If a use case requires expressions like `count_one_bits(BITMASK)`,
the expression language will need to be extended.

### 6.6 NULL Handling for Unexported Array Slots

When a `pin` declaration with a trailing `if` clause produces unexported
slots, those slots are initialized to `NULL` in `system.c`. The block author
is responsible for checking for `NULL` before dereferencing. Whether the
framework should provide a helper macro or assertion for this check is
deferred.

### 6.7 Namespace Collision in Mutually Exclusive `#if` Blocks

The parser performs namespace collision detection at parse time, before
parameter values are known. As a result, two declarations with the same
name in mutually exclusive `#if` blocks — such as `#if PARAM` and
`#if !PARAM` — are incorrectly reported as a collision even though only
one branch can ever be active for any given set of parameter values.
Block authors must use distinct names for declarations in mutually
exclusive `#if` blocks. A future `#else` construct could allow the parser
to detect mutual exclusivity and suppress the false collision, but is not
currently considered a priority.
---

## 7. Examples

**Note:** These examples are currently aspirational; they display
what we intend the tool(s) to generate.  Once the tools are working,
the `Generated  xxx.x` sections will be replaced with the actual
generated output.

### 7.1 limit1 — Simple Non-Variant Block

A block with four scalar pins and no variants. Demonstrates the minimal
`.bloc` file structure, block-level metadata, and per-pin metadata.

**`limit1.bloc`:**

```
block limit1 /// Clamps input to [min, max] range.
             /// Both bounds are inclusive.

// pins declared in expected access order
pin float  input   in   /// value to be clamped
pin float  output  out  /// clamped result
pin float  input   min  /// lower bound (inclusive)
pin float  input   max  /// upper bound (inclusive)

function update  /// clamp in to [min, max] and write result to out
```

**Generated `limit1.h`:**

```c
// Auto-generated by the EMBLOCS block compiler. Do not edit.
// Source: limit1.bloc

#ifndef LIMIT1_H
#define LIMIT1_H

#include "emblocs_comp.h"

#define BL_CONCAT(a, b)  a##b
#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)

typedef struct {
    pin_float_t *in_;
    pin_float_t *out_;
    pin_float_t *min_;
    pin_float_t *max_;
} BL_MANGLE(t);

typedef BL_MANGLE(t) self_t;

#define IN_   (*self->in_)
#define OUT_  (*self->out_)
#define MIN_  (*self->min_)
#define MAX_  (*self->max_)

#endif // LIMIT1_H
```

**Generated `limit1.c` template:**

```c
#include "limit1.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    // TODO: implement update
    // Pins available:
    //   IN_, OUT_, MIN_, MAX_  (always present)
}
```

**`limit1.c` after block author implementation:**

```c
#include "limit1.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;

    float val = IN_;
    if (val > MAX_) val = MAX_;
    if (val < MIN_) val = MIN_;
    OUT_ = val;
}
```

### 7.2 integrator — Boolean Variant Parameters

A block with two optional pins controlled by boolean parameters. Demonstrates
`param`, `#if`/`#endif`, and the `BL_MANGLE` pattern with conditional pins.

**`integrator.bloc`:**

```
block integrator  /// Integrates input over time.
                  /// Optional enable and hold pins control integration behavior.

param bool HAS_ENABLE  default=0  /// if true, export the enable pin
param bool HAS_HOLD    default=0  /// if true, export the hold pin

pin float  input   in      /// value to integrate
pin float  output  out     /// integral of in over time

#if HAS_ENABLE
pin bool   input   enable  /// when false, resets out to zero and halts integration
#endif

#if HAS_HOLD
pin bool   input   hold    /// when true, holds out constant without resetting
#endif

var float accumulated;     // integration state

function update  /// periodic integration step
```

**Generated `integrator.h`:**

```c
// Auto-generated by the EMBLOCS block compiler. Do not edit.
// Source: integrator.bloc

#ifndef INTEGRATOR_H
#define INTEGRATOR_H

#include "emblocs_comp.h"

#ifndef BL_HAS_ENABLE
#define BL_HAS_ENABLE (0)
#endif
#ifndef BL_HAS_HOLD
#define BL_HAS_HOLD (0)
#endif

#define BL_CONCAT(a, b)  a##b
#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)

typedef struct {
    pin_float_t *in_;
    pin_float_t *out_;
#if BL_HAS_ENABLE
    pin_bool_t  *enable_;
#endif
#if BL_HAS_HOLD
    pin_bool_t  *hold_;
#endif
    float accumulated;
} BL_MANGLE(t);

typedef BL_MANGLE(t) self_t;

#define IN_  (*self->in_)
#define OUT_ (*self->out_)
#if BL_HAS_ENABLE
#define ENABLE_ (*self->enable_)
#endif
#if BL_HAS_HOLD
#define HOLD_ (*self->hold_)
#endif

#endif // INTEGRATOR_H
```

**Generated `integrator.c` template:**

```c
#include "integrator.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    // TODO: implement update
    // Pins available:
    //   IN_, OUT_  (always present)
#if BL_HAS_ENABLE
    //   ENABLE_   (conditional on BL_HAS_ENABLE)
#endif
#if BL_HAS_HOLD
    //   HOLD_     (conditional on BL_HAS_HOLD)
#endif
}
```

### 7.3 mux — Integer Variant Parameters and Array Pins

A multiplexor block with 2D array pins driven by integer parameters.
Demonstrates `param` with `min`/`max`, array pin declarations with index
variables, name templates, and cache-friendly storage ordering that differs
from name ordering.

**`mux.bloc`:**

```
block mux /// N-channel M-to-1 multiplexor.
          /// All channels share a single select input.

param u32 NUM_CHAN  default=1  min=1  max=16  /// number of independent channels
param u32 NUM_INPUT default=2  min=2  max=10  /// number of inputs per channel

// storage order [NUM_INPUT][NUM_CHAN] for cache efficiency:
// all channels for one select value are contiguous in memory
pin raw  input   ch{c:2}_in{i:1}[i=NUM_INPUT][c=NUM_CHAN]  /// mux input
pin raw  output  ch{c:2}_out[c=NUM_CHAN]                   /// mux output
pin u32  input   select                                    /// selects active input (0-based)

function update  /// copy in[select][ch] to out[ch] for all channels
```

The name template uses index variable `c` (channel) for the leading part of
the pin name and `i` (input number) for the trailing part, regardless of
their order in the storage layout. `ch01_in2` refers to channel 1, input 2,
stored at `self->ch00_in0_[2][1]`.

**Generated `mux.h`:**

```c
// Auto-generated by the EMBLOCS block compiler. Do not edit.
// Source: mux.bloc

#ifndef MUX_H
#define MUX_H

#include "emblocs_comp.h"

#ifndef BL_NUM_CHAN
#define BL_NUM_CHAN (1)
#endif
#ifndef BL_NUM_INPUT
#define BL_NUM_INPUT (2)
#endif

#define BL_CONCAT(a, b)  a##b
#define BL_MANGLE(name)  BL_CONCAT(BL_BLOCK_NAME, _##name)

typedef struct {
    pin_raw_t *ch00_in0_[BL_NUM_INPUT][BL_NUM_CHAN];
    pin_raw_t *ch00_out_[BL_NUM_CHAN];
    pin_u32_t *select_;
} BL_MANGLE(t);

typedef BL_MANGLE(t) self_t;

#define CH00_IN0_  (self->ch00_in0_)
#define CH00_OUT_  (self->ch00_out_)
#define SELECT_    (*self->select_)

#endif // MUX_H
```

**Generated `mux.c` template:**

```c
#include "mux.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;  // delete this line if periodns is used

    // TODO: implement update
    // Pins available:
    //   CH00_IN0_[BL_NUM_INPUT][BL_NUM_CHAN]  (raw input array)
    //   CH00_OUT_[BL_NUM_CHAN]                (raw output array)
    //   SELECT_                               (u32 select input)
}
```
**`mux.c` after block author implementation:**

```c
#include "mux.h"

void BL_MANGLE(update)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;

    uint32_t sel = SELECT_;
    if (sel >= BL_NUM_INPUT) return;  // out of range, do nothing

    for (int c = 0; c < BL_NUM_CHAN; c++) {
        *self->ch00_out_[c] = *self->ch00_in0_[sel][c];
    }
}
```

### 7.4 gpio — Bitmask Parameters and Sparse Arrays

A GPIO port driver that exports EMBLOCS pins only for hardware pins specified
in bitmask parameters. Demonstrates `#if`/`#endif` for conditional array
allocation, the trailing `if` clause for sparse slot export, index variables
in name templates, `var` declarations, and multiple functions.

The struct always contains fixed-size arrays (one slot per possible hardware
pin). Slots corresponding to hardware pins not included in a bitmask are
initialized to `NULL` in `system.c` and skipped at runtime.

**`stm32_gpio.bloc`:**

```
block stm32_gpio /// STM32 GPIO port driver with per-pin EMBLOCS interface.
                 /// Each bit set in a bitmask parameter exports one EMBLOCS pin.
                 /// Array slots for unselected pins are NULL and must not be
                 /// dereferenced.

param u32 INPUTS   default=0x0000  /// bitmask: bits selecting pins to export as inputs
param u32 OUTPUTS  default=0x0000  /// bitmask: bits selecting pins to export as outputs
param u32 ENABLES  default=0x0000  /// bitmask: bits selecting pins to export as output-enables

var GPIO_TypeDef *base_addr;    // hardware register base address

// Each array is conditionally allocated; if no pins of a given direction are
// needed, the array is omitted from the struct entirely.
// Within an allocated array, only selected slots are exported as EMBLOCS pins.

#if INPUTS!=0
pin bool  output  pin{i:2}_in[i=16]   if (INPUTS>>i)&1   /// GPIO input value
#endif

#if OUTPUTS!=0
pin bool  input   pin{i:2}_out[i=16]  if (OUTPUTS>>i)&1  /// GPIO output value
#endif

#if ENABLES!=0
pin bool  input   pin{i:2}_oe[i=16]   if (ENABLES>>i)&1  /// GPIO output enable
#endif

function read   /// sample IDR and update input pins; call early in thread
function write  /// read output and enable pins, drive ODR/BSRR; call late in thread
```

**Generated `stm32_gpio.h` (excerpt):**

```c
#ifndef BL_INPUTS
#define BL_INPUTS (0)
#endif
#ifndef BL_OUTPUTS
#define BL_OUTPUTS (0)
#endif
#ifndef BL_ENABLES
#define BL_ENABLES (0)
#endif

typedef struct {
    GPIO_TypeDef *base_addr;
#if BL_INPUTS != 0
    pin_bool_t *pin00_in_[16];
#endif
#if BL_OUTPUTS != 0
    pin_bool_t *pin00_out_[16];
#endif
#if BL_ENABLES != 0
    pin_bool_t *pin00_oe_[16];
#endif
} BL_MANGLE(t);
```

**`stm32_gpio.c` implementation (read function):**

```c
void BL_MANGLE(read)(void *instance_data, uint32_t periodns) {
    self_t *self = (self_t *)instance_data;
    (void)periodns;

#if BL_INPUTS != 0
    uint32_t idr = self->base_addr->IDR;
    for (int i = 0; i < 16; i++) {
        if (self->pin00_in_[i] != NULL) {
            *self->pin00_in_[i] = (idr >> i) & 1;
        }
    }
#endif
}
```

## 8. Quick Reference

### 8.1 Statements

| Statement | Syntax | Section |
|-----------|--------|---------|
| `block` | `block <name> /// description` | 3.1 |
| `param` | `param <type> <NAME> default=<value> [min=<value>] [max=<value>]` | 3.2 |
| `pin` | `pin <type> <direction> <name-spec> [if <expr>]` | 3.3 |
| `var` | `var <C-declaration>;` | 3.4 |
| `function` | `function <name>` | 3.5 |
| `#if` | `#if <expr>` | 4.1 |
| `#endif` | `#endif` | 4.1 |

### 8.2 Pin Name Specification

| Form | Example | EMBLOCS names | Field name |
|------|---------|---------------|------------|
| Scalar | `foo` | `foo` | `foo_` |
| Scalar with specifier | `stage{STAGE:1}` | e.g. `stage3` | `stage0_` |
| 1D array | `ch{i:2}_out[i=NCHAN]` | `ch00_out`, `ch01_out`, ... | `ch00_out_` |
| 2D array | `ch{i:2}_in{j:1}[i=NCHAN][j=NINPUT]` | `ch00_in0`, `ch00_in1`, ... | `ch00_in0_` |
| 1D sparse | `pin{i:2}_in[i=16] if (MASK>>i)&1` | depends on MASK | `pin00_in_` |

### 8.3 Name Template Format Specifier

Format specifiers appear within the name portion of a pin name-spec:

    {expr:N}

| Part | Description |
|------|-------------|
| `expr` | An expression (see 8.5); may reference parameters and in-scope index variables |
| `N` | A single digit 1-9; field width in name, zero-padded |

The field name is derived by replacing each `{expr:N}` with `N` zeros and appending `_`.

### 8.4 Array Dimension Specifier

Dimension specifiers are appended directly to the name template, one per dimension:

    [varname=size]

| Part | Description |
|------|-------------|
| `varname` | A valid identifier; names the index variable for this dimension |
| `size` | An expression (see 8.5); must evaluate to a positive integer |

The index variable takes values 0 to `size`-1 and is in scope for the name template and trailing `if` condition of the same pin declaration. It may not collide with a parameter name or another index variable on the same pin.

### 8.5 Expression Operands and Operators

**Operands:**

| Operand | Example |
|---------|---------|
| Integer literal (decimal) | `42` |
| Integer literal (hexadecimal) | `0xFF` |
| Parameter name | `NCHAN` |
| Index variable (in pin declarations) | `i` |

**Operators:**

| Operator | Meaning |
|----------|---------|
| `+`, `-`, `*`, `/`, `%` | Arithmetic |
| `>>`, `<<` | Bitwise shift |
| `&`, `\|`, `^`, `~` | Bitwise AND, OR, XOR, NOT |
| `==`, `!=`, `<`, `>`, `<=`, `>=` | Comparison |
| `&&`, `\|\|`, `!` | Logical AND, OR, NOT |
| `( )` | Grouping |

Note: expressions must be written as a single token with no internal whitespace.

### 8.6 Parameter Types and Value Ranges

| Type | Valid values | Notes |
|------|-------------|-------|
| `bool` | `0` or `1` | values outside this range produce a warning |
| `u32` | `0` to `4294967295` (0xFFFFFFFF) | `min=` and `max=` can further restrict the range |

---

## 9. Build System Notes

This section captures design decisions and open problems relating to the
build system integration of the two-tool model. These are not part of the
`.bloc` language specification but are recorded here to inform future
implementation work.

### 9.1 Dependency Graph

The build dependency graph flows cleanly with no circular dependencies:

```
<block>.bloc ──→ [Tool 1, template mode] ──→ <block>.h   (always regenerated)
                                         └──→ <block>.c  (generated only if missing)

<block>.bloc ──→ [Tool 1, variant mode]  ──→ <variant>.h
system.blocs ─┘  (params from blockdef)  ├──→ <variant>.c
                                         └──→ <variant>.json

<variant>.json ──→ [Tool 2] ──→ system.c
                             └──→ system.cmake

<variant>.c ──→ [C compiler] ──→ <variant>.o
system.c + <variant>.h ──→ [C compiler] ──→ system.o
<variant>.o + system.o ──→ [linker] ──→ firmware.elf
```

### 9.2 File Locations

Files are divided into two categories:

**Library source** — live alongside `<block>.bloc` in the block's library,
checked into source control:

| File | Owner | Notes |
|------|-------|-------|
| `<block>.bloc` | Block author | Hand-written |
| `<block>.c` | Block author | Hand-written after initial generation; never overwritten by Tool 1 |
| `<block>.h` | Tool 1 | Generated; do not hand-edit; checked in to support editor tooling without requiring a prior build |

CI should verify that the checked-in `<block>.h` matches what Tool 1 would
generate from the current `<block>.bloc`.

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

### 9.3 CMake Integration

The master `CMakeLists.txt` is hand-written and stable. It includes the
generated `system.cmake`:

```cmake
include(${CMAKE_BINARY_DIR}/system.cmake)
```

The generated `system.cmake` contains one `add_library(... OBJECT ...)` rule
per variant, compiling the generated `<variant>.c` directly with no `-D`
flags required:

```cmake
add_library(mux2to1 OBJECT ${CMAKE_BINARY_DIR}/mux2to1.c)
```

A CMake custom command declares `<block>.h` as the output of Tool 1 template
mode with `<block>.bloc` as its dependency, so `<block>.h` is automatically
regenerated when the `.bloc` file changes:

```cmake
add_custom_command(
    OUTPUT ${block}.h
    COMMAND bloc_compiler.py ${block}.bloc --mode=template
    DEPENDS ${block}.bloc
)
```

Tool 1 (variant mode) and Tool 2 are declared as CMake custom commands with
`system.blocs` as their primary dependency, so they re-run automatically
when the `.blocs` file changes.

### 9.4 Over-triggering Problem and Mitigation

The `.blocs` file has two distinct regions with very different rates of
change: the structural region (`blockdef`/`block` commands, rarely changed)
and the wiring region (signal connections and value assignments, changed
frequently during tuning). Edits to the wiring region unnecessarily
re-trigger Tool 1 variant mode even though no structural change occurred.

The preferred mitigation is stable-output detection: all three variant-mode
output files (`<variant>.h`, `<variant>.c`, `<variant>.json`) are written
only if their content has actually changed. If the files are unchanged, their
timestamps are not updated and CMake does not retrigger downstream C
compilation. This reduces the over-triggering problem to a minor latency
issue — Tool 1 still runs on every `.blocs` edit, but the C compiler and
linker only re-run when something structural actually changed.

### 9.5 Future Possibility: Split `.blocs` File

A more complete solution would split `system.blocs` into two files: a
structural file (e.g., `blockdefs.blocs`) containing only `blockdef` and
`block` commands, and a wiring file. Only the structural file would trigger
Tool 1 re-invocation. Deferred pending evidence that stable-output detection
is insufficient in practice.
