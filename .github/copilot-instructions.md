# EMBLOCS workspace guidance for AI coding agents

This repository contains two fairly distinct halves: a **host‑side Python toolkit** used for development and a **tiny embedded C framework** (EMBLOCS) that runs on ARM32/STM32 targets.  Agents should understand both domains and the way they interoperate.

## 🗂️ High‑level architecture

- `python/` – Tkinter GUI, serial port widget, scope display, command console.  All of the host tools live here along with a simple JSON configuration mechanism (`AppConfig`).  `emblocs_gui.py` is the main entry point.
- `src/emblocs` – core library implementing the block/thread/signal API (`bl_*` functions) plus parsing and "show" helpers.
- `src/components` – modular components (mux2, sum2, watch, perftimer, etc.).  Each component is a self‑contained C pair with a setup function, runtime code and metadata definitions.  New components follow this template.
- `src/misc` – utility code used by both core and projects (linked list, printing, serial, string conversion, etc.).
- `src/projects/...` – concrete applications for particular boards.  `B-G431B-ESC1/main/` contains the reference project with `main.c`, `emblocs_config.h`, Makefile and linker script.  Projects configure pins, create `bl_comp_defs[]` and supply token arrays for runtime configuration.

The host and device communicate over a simple serial protocol: **ASCII text interleaved with binary packets**.  A byte ≥0x80 marks the start of a binary packet; the low‑7 bits are the packet address (0‑127) allowing packets to be routed to separate buffers (see `src/misc/serial.h`).  The payload is COBS‑encoded and terminated with a 0x00 byte.  The Python `SerPort` widget now implements this protocol with two background threads:

  * **receive thread** – reads bytes from the port, separates ASCII from packet data, decodes COBS and queues `(addr,data)` tuples.
  * **transmit thread** – drains two queues (text and packets), performing COBS encoding on outgoing packets before sending.

Commands sent from the host are plain text; replies are text and may include `show` command outputs.  The GUI currently displays received packet metadata in the console tab.

## ⚙️ Developer workflows

1. **Embedded build**
   - Add or edit project in `src/projects/<MCU>/<board>/…`.  `main/Makefile` includes `../header.mk`, which climbs to the top of the tree and sets up paths.
   - Supply a `local.mk` (not tracked) in the repo root with `BINUTILS_ROOT`, `PACKAGE_ROOT` and optionally `SHELL`/`PATH`.  This points to `arm‑none‑eabi` toolchain and STM32Cube library.
   - From the project `main` directory run `make` (or `make clean`, `make all`).  Output is under `build/` and `main.hex` is produced.
   - Flashing is done with external utilities (OpenOCD, st‑flash, etc.) not included here.
   - CMake support exists (see `CMakeLists.txt` files) but the canonical build uses plain Make.  The CMake artifacts are related to using the emblocs code under the Raspberry Pi Pico SDK, which is a future goal.
   - Ensure Python 3 with `tkinter` and `pyserial` installed (`pip install pyserial`).
   - Run `python/python/emblocs.py` or make the script executable.
   - Configuration persists in `python/emblocs.json`.  Widgets expose a `add_config_data()` static method – call these when expanding configuration.
   - `python/testing.py` was an exploration of storing the embedded configuration in JSON format; it may or may not be useful in the future.

3. **Debug / inspection**
   - Use the console tab in the GUI to send commands such as `show blocks`, `watch add`, etc.
   - Embedded code uses `printing.c` for text output and `watch` component for realtime variable inspection.
   - The `bl_show_*` functions dump metadata over serial; the parse library (`bl_parse_*`) is used internally by the command interpreter.

## 📝 Coding conventions / patterns

### C / firmware

- **No dynamic allocation** at runtime except during component setup.  Most memory is allocated once via `bl_block_create()`; `malloc()` is only used for helper strings and names in setup functions.
- Each component file follows a standard pattern:
  1. config and runtime data structs (aligned to 32‑bit boundary).
  2. `bl_function_def_t` arrays listing realtime functions.
  3. a `*_setup()` function that validates the personality, creates a block sized for `personality`‑dependent data, adds pins via `bl_block_add_pin()`, and finally registers functions with `bl_block_add_functions()`.
  4. static comp_def structures of type `bl_comp_def_t` with `BL_NEEDS_PERSONALITY` or other flags.
  5. realtime functions marked `__time_critical_func` and taking `(void *ptr, uint32_t period_ns)`.
- Use macros defined in `emblocs_common.h` such as `CHECK_NULL`, `CHECK_RETURN`, `TO_BLOCK_SIZE`, `ERROR_RETURN`, `BL_TYPE_*`, `BL_DIR_*`, and assert maximum pins / block size with `_Static_assert`.
- Max pins / data sizes are constants (`BL_PIN_COUNT_MAX`, `BL_BLOCK_DATA_MAX_SIZE`).  Update asserts when increasing limits.
- Global component definitions are added to the `bl_comp_defs[]` array in the project's `main.c`.  Only components listed here can be instantiated from the command parser.
- `emblocs_config.h` holds project‑specific compile‑time options and watch pin configurations; projects include it from `main.c`.
- The build system uses a layered Makefile (`header.mk` ➜ `include.mk`) to collect source paths, toolchain flags, include directories and object lists (`EMBLOCS_OBJS`, `COMP_OBJS`).  Add new component `.o` names to `COMP_OBJS` or let the array expand automatically.

### Python / host

- Widgets are `ttk.Frame` subclasses with a constructor accepting `(parent, config, **kwargs)` and a static `add_config_data(config)` method for adding required keys.
- The `AppConfig` class merges command‑line args and JSON file values; new GUI modules should augment `AppConfig` in their `add_config_data()`.
- The serial communication protocol is decoded in a separate thread (`SerPort._rx_worker()`); a second thread handles outgoing data.  Two queues carry pending text and packet data.  Use `put_tx_text()` or `put_tx_packet(addr,data)` and `get_rx_text_tuple()` / `get_rx_packet()` to interact with the port.
- Use `after()` scheduling to poll the queues and update widgets (`update_console()` in `EmblocsGUI`).
- Styling is minimal; fonts are determined via configuration.

## 🔄 Project‑specific conventions

- **Command syntax**: the embedded `bl_parse_*` library splits strings on whitespace and executes commands like `block new foo rgb_merge 8 3` etc.  Many examples appear in `main.c` tokens arrays.
- **Binary blocks**: first byte &ge;128 indicates upcoming raw data; Python `SerPort` expects this pattern and queues blocks separately from text lines.
- `*.json` files (e.g. `emblocs.json`, `sample.json`) follow simple nested dict/list schemas; `testing.py` shows the validation pattern.
- When adding a new project copy an existing directory, update the MCU-specific Makefile variables (`MCU_PKG`, `DEFS`, include paths) and provide appropriate linker script.

## 📦 External dependencies

- **ARM GCC toolchain** (`arm-none-eabi-*`) – referenced via `BINUTILS_ROOT` in `local.mk`.
- **STM32Cube packages** – path provided by `PACKAGE_ROOT` in `local.mk`.
- **Python** – requires `pyserial` and a working `tkinter` installation; no other third‑party modules.
- The code is designed to run on bare‑metal or lightweight RTOS (FreeRTOS, ThreadX).  No OS or dynamic memory is assumed on the target.

---

> 💡 **Tip for agents**: when editing core C code, mimic the style and function signatures already present.  When extending Python UI, follow the example of existing widgets and keep UI‑thread work inside `after()` callbacks.  Refer to `main.c` and any component file for concrete command tokens and common idioms.

If anything above is unclear or you need more detail on a specific area, please point it out so I can refine these instructions.