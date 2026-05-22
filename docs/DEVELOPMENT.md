# EMBLOCS Development Notes

This document captures implementation decisions, conventions, and current
state that are not part of the language or architecture specifications.
It is updated as development progresses and will be reorganized into the
main documentation at a future date.

---

## 1. Python Toolchain Structure

### 1.1 File Organization

All Python source files live in `python/`. There are no packages; all
modules are peers in the same directory.

| File | Role |
|------|------|
| `emblocs.py` | Shared object model: BlockSpec, BlockDef, Design, and all related classes |
| `parse_common.py` | Shared parser infrastructure: Token, Severity, ErrorContext, report() |
| `expressions.py` | Expression evaluator for .bloc parameter expressions |
| `bloc_parser.py` | Parser for .bloc block template files → BlockSpec |
| `bloc_resolver.py` | Resolver: BlockSpec + params → BlockDef |
| `blocs_parser.py` | Parser for .blocs system definition files → Design |
| `blocs_output.py` | Serializer: Design → .blocs format output |

### 1.2 Three-Stage Parsing Pipeline

Both parsers follow the same three-stage structure:

1. **File/string reading** — `read_source_file()` or `read_source_string()` in
   `parse_common.py`. Handles file I/O, UTF-8 validation, ASCII checking, and
   pushes an `ErrorContext` onto the context stack. Caller must pop when done.

2. **Lexing** — language-specific. `.bloc` lexer handles `//` comments and
   `///` descriptions. `.blocs` lexer handles `#` comments and `\` line
   continuation. Both produce a list of logical lines, each a list of `Token`
   objects with physical line and column numbers.

3. **Parsing** — `parse_statement()` (`.bloc`) or `parse_command()` (`.blocs`)
   dispatches each logical line to a per-keyword handler.

Public entry points follow the pattern:
- `parse_xxx_file(path)` — reads file, lexes, parses, returns object or None
- `parse_xxx_string(text)` — same but from a string; used primarily for testing
- `parse_xxx(lines)` — core function taking pre-read lines; expects active context

### 1.3 Error Reporting

All error reporting goes through the module-level `ctx` instance of
`ErrorContext` in `parse_common.py`. Key rules:

- `ctx.set(token=tok)` updates the current source location before processing
  each token; subsequent error calls use this location automatically
- `ctx.error()`, `ctx.warning()`, `ctx.info()`, `ctx.fatal()` report
  diagnostics using the current location from the context stack
- Context location can be overridden by passing `source=str`, `token=tok`,
  `lineno=n`, or `column=n` to any reporting call.
- Passing `source=OMIT`, `lineno=OMIT` or `column=OMIT` explicitly
  suppresses that field from the output regardless of the context value.
- `ctx.fatal()` calls `sys.exit(1)` — use only for truly unrecoverable
  situations (file not found, wrong encoding). Parser syntax errors use
  `ctx.error()`
- Each parser pushes a new context frame at the start via `ctx.push()` and
  pops it at the end via `ctx.pop()`; `ctx.summarize()` is called before
  popping to print error/warning/info counts


### 1.4 Bloc Spec Cache

`blocs_parser.py` maintains a module-level cache of parsed `BlockSpec` objects:

```python
_bloc_spec_cache: dict[str, BlockSpec] = {}
```

Keyed by normalized POSIX path. When a `blockdef` command references a `.bloc`
file that has already been parsed, the cached `BlockSpec` is reused. This
allows multiple variants of the same block to be defined without re-parsing
the `.bloc` file each time.

---

## 2. Object Model

### 2.1 Class Hierarchy

```
BlockSpec-level (from .bloc parser):
    ParamSpec, DimSpec, PinSpec, VarDef, FunctSpec, Statement, BlockSpec

BlockDef-level (from resolver):
    PinDef, FunctDef, BlockDef

Design-level (from .blocs parser):
    Signal, PinInstance, FunctInstance, BlockInstance, Thread, Design
```

### 2.2 Design Methods

`Design` in `emblocs.py` provides methods for all system-building operations.
Parsers call these methods; the methods validate and execute the operation.
Errors are raised as `EmblocsError` exceptions; parsers catch them and call
`ctx.error()` with the appropriate message.

The public API provides object-based primary methods and name-based convenience
wrappers:

| Method | Description |
|--------|-------------|
| `add_block_def(block_def)` | Add a resolved BlockDef to the Design |
| `add_block_instance(name, block_def_name)` | Create a named block instance |
| `add_signal(name, sig_type)` | Create a named signal |
| `add_thread(name, period_ns)` | Create a named thread |
| `set_value(obj, value)` | Set value of a signal or unconnected pin |
| `link(obj1, obj2)` | Connect a pin to a signal, or a function to a thread |
| `unlink(obj)` | Disconnect a pin or function |
| `set_value_by_name(name, value)` | Name-based wrapper for set_value |
| `link_by_name(name1, name2)` | Name-based wrapper for link |
| `unlink_by_name(name)` | Name-based wrapper for unlink |
| `find_child_by_name(name)` | Look up a direct child of Design by name |
| `find_object_by_name(name)` | Look up any object including block.pin dotted names |

### 2.3 Dummy Signals

Every pin in a `BlockInstance` is always connected to a signal — either a
named signal or a private dummy signal. Dummy signals are created automatically
when a block instance is created, named `__<instance>__<pin>`, stored in
`Design.dummy_signals` (separate from `Design.signals`), and marked with
`Signal.is_dummy = True`. This allows `set_pin_value()` to work without special
cases, and preserves pin values across connect/disconnect cycles.

### 2.4 Namespace

All block definitions, block instances, signals, and threads share one flat
namespace enforced by `Design.namespace` (a `dict[str, object]`). In addition
to ensuring name uniqueness, the namespace allows O(1) lookup of an object
by name even if its type is unknown; the type can then be checked after
lookup.
Dummy signal names are not in the namespace — their `__block__pin` naming
convention ensures uniqueness without namespace pollution.

---

## 3. Testing Conventions

### 3.1 Test File Organization

```
python/tests/
    conftest.py          # shared fixtures
    test_expressions.py  # expression evaluator tests
    test_parse_common.py # parse_common.py tests
    test_bloc_parser.py  # bloc_parser.py tests
    test_blocs_parser.py # blocs_parser.py tests
    test_emblocs.py      # emblocs.py Design method tests
    data/
        good/            # valid input files for happy-path tests
        bad/             # invalid input files for error tests
        tmp/             # generated test files (in .gitignore)
```

### 3.2 Test Conventions

- **Exact message matching** — always check the complete error/warning message
  using the REPLACE_ME trick: write `expected = "REPLACE_ME"`, run the test,
  capture the actual output, paste it as the expected string. Never use fragment
  matching (`assert "fragment" in message`).

- **Assert both message and result** — for failure cases, assert both the exact
  error message AND that the return value is `None`:
```python
  assert actual == expected, (...)
  assert design is None
```

- **String-based testing** — use `parse_bloc_string()` and
  `parse_blocs_string()` for most tests. File-based tests are only needed when
  testing file I/O behavior specifically.

- **Context stack cleanup** — every test class uses the `clean_context`
  fixture (autouse=True) to ensure the context stack is clean before and after
  each test.

- **Generated test files** — write to `tests/data/tmp/` for predictable paths
  in error messages. This directory is in `.gitignore`.

- **Cache cleanup** — tests that exercise `blocs_parser.py` use the
  `clear_cache` fixture to reset `_bloc_spec_cache` between tests.

### 3.3 Code Style

- No blank lines in function bodies — use comment lines to separate phases
- Exact error messages are tested; changing a message requires updating tests
- `Severity.FATAL` is reserved for unrecoverable I/O errors; all parser errors
  use `Severity.ERROR`

---

## 4. Current Implementation State

### 4.1 Completed and Tested

- `expressions.py` — expression evaluator with full test coverage
- `parse_common.py` — shared infrastructure with full test coverage;
  `ErrorContext` class with module-level `ctx` instance
- `bloc_parser.py` — .bloc file parser with full test coverage
- `bloc_resolver.py` — BlockSpec → BlockDef resolver; no dedicated test suite
- `emblocs.py` — Design object model with full test coverage of all methods
- `blocs_parser.py` — complete: lexer, all creation commands, all subcommand
  handlers (`=`, `+`, `-`, `-+`), full test coverage
- `blocs_output.py` — Design → .blocs serializer; manually tested

### 4.2 Known Gaps and Deferred Items

- `bloc_resolver.py` has no dedicated test suite
- `blocs_output.py` has no automated test suite
- `.bloc` file path handling in `blockdef` commands currently stores the
  original relative path; a tag-based library path system is planned but
  deferred until real project experience informs the design
- Code generation (Tool 1 template mode, Tool 1 variant mode, Tool 2) not yet started
- Runtime monitor not yet started
- CMake integration not yet started
