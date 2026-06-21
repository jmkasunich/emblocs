# emblocs_common.py
# Shared infrastructure for EMBLOCS tools.
# Provides Config for managing tool configuration data across
# GUI and command-line tools, reading from and writing to a
# shared JSON config file.

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

from parse_common import ctx, OMIT


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    """
    Manages configuration data for EMBLOCS tools.

    Configuration data is stored in a single nested dict (config.data)
    and accessed using dotted names, e.g. 'scope.channel_00.units_per_div'.
    Data items can be loaded from files or the command line, and saved
    to files.

    Consumer classes register their keys by calling set_by_name() with
    default values during initialization.  This establishes both the
    existence and expected type of each key.  load_file() may be called
    one or more times to merge file contents into config.data; later
    calls take precedence over earlier ones for overlapping keys.
    merge_cli() applies command line values; if called last, it gives
    them highest precedence.

    Typical usage:

        config = Config()

        # register keys with defaults by calling set_by_name()
        config.set_by_name('paths.bloc_search_paths', [])
        config.set_by_name('text.font_size', 12)
        # client class sets its own keys and CLI args
        SerPort.register_config(config)

        # set up CLI args
        # --cfg is not mapped to a config name, used to find the config file
        config.add_cli_arg('--cfg', help="path to config file")
        # --font-size is mapped to a config value
        config.add_cli_arg('--font-size', name='text.font_size', help="font size for text window")
        # --verbose is not, used only by the main program
        config.add_cli_arg('--verbose', action='store_true', help="verbose output")

        # parse CLI first so we can use --cfg to find the config file
        args = config.parse_cli()

        # load config file(s); caller decides policy
        template = Path(__file__).parent.parent / 'emblocs_cfg.json'
        if template.exists():
            # load template fields and values first
            config.load_file(template)
        cfg_path = Path(args.cfg) if args.cfg else Path('emblocs_cfg.json')
        # project config overrides template; if not found,
        # one will be created by save_file() on exit
        if cfg_path.exists():
            # config file values override template
            # config file can also add new fields
            config.load_file(cfg_path)

        # CLI values last so they override file values
        config.merge_cli()

        # ... use config ...

        config.save_file(cfg_path)

    Typical usage in a consumer class:

        class SerPort:
            @classmethod
            def register_config(cls, config):
                config.set_by_name('port.port', '')
                config.set_by_name('port.baud', '115.2K')
                config.add_cli_arg('-p', '--port', name='port.port',
                                   help="serial port name")
                config.add_cli_arg('-b', '--baud', name='port.baud',
                                   help="baud rate")

            def __init__(self, config):
                self.cfg = config.get_by_name('port')
                # access as self.cfg['port'], self.cfg['baud'], etc.
                # or use config.get_by_name('port.port') directly
    """

    def __init__(self) -> None:
        self.data:     dict                       = {}    # single source of truth
        self._cli_map: list[tuple[str, str]]      = []    # (dest, name) for mapped args
        self._args:    argparse.Namespace | None  = None  # saved by parse_cli()
        self._parser:  argparse.ArgumentParser    = argparse.ArgumentParser()

    # ------------------------------------------------------------------
    # Name-based access
    # ------------------------------------------------------------------

    def set_by_name(self, name: str, value) -> None:
        """
        Set a config value using dotted name notation.
        e.g. 'scope.channel_00.units_per_div'

        If the name does not exist, it is created along with any
        intermediate dicts needed to reach it.

        If the name already exists, the new value is type-checked against
        the existing value.  A type mismatch emits a warning and leaves
        the existing value unchanged.  This protects registered defaults
        from being overwritten by a file containing a wrongly-typed value,
        while still allowing the value to be updated by a correctly-typed
        file or CLI value.

        bool is treated as distinct from int even though Python's bool
        is a subclass of int.
        """
        parts = name.split('.')
        node = self.data
        # traverse to the parent of the leaf, creating dicts as needed
        for part in parts[:-1]:
            if part not in node:
                node[part] = {}
            elif not isinstance(node[part], dict):
                ctx.error(
                    f"'{name}': '{part}' is already set as a leaf value; "
                    f"cannot use it as an intermediate node",
                    source=OMIT, lineno=OMIT, column=OMIT,
                )
                return
            node = node[part]
        # set or type-check the leaf
        leaf = parts[-1]
        if leaf not in node:
            node[leaf] = value
        else:
            existing = node[leaf]
            type_ok = (
                isinstance(existing, bool) and isinstance(value, bool)
            ) or (
                not isinstance(existing, bool) and
                type(value) is type(existing)
            )
            if type_ok:
                node[leaf] = value
            else:
                ctx.warning(
                    f"'{name}' has wrong type "
                    f"(expected {type(existing).__name__}, "
                    f"got {type(value).__name__}); "
                    f"keeping current value {existing!r}",
                    source=OMIT, lineno=OMIT, column=OMIT,
                )

    def get_by_name(self, name: str):
        """
        Retrieve a value using dotted name notation.
        e.g. 'scope.channel_00.units_per_div'

        If the name resolves to a leaf value, that value is returned.
        If the name resolves to a dict, that dict is returned; this
        allows retrieval of an entire subtree, e.g. get_by_name('scope')
        returns the entire scope section.
        Raises KeyError if any component of the name is not found.
        """
        parts = name.split('.')
        node = self.data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                raise KeyError(f"config name '{name}' not found")
            node = node[part]
        return node

    def name_exists(self, name: str) -> bool:
        """
        Return True if the given dotted name exists in config.data,
        False otherwise.
        """
        try:
            self.get_by_name(name)
            return True
        except KeyError:
            return False

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def _traverse(self, d: dict, prefix: str = '') -> Iterator[tuple[str, object]]:
        """
        Recursively yield (name, value) pairs for every leaf in d,
        where name is the full dotted path to the leaf.
        Dicts are traversed; all other values are treated as leaves.
        """
        for key, val in d.items():
            full_name = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                yield from self._traverse(val, full_name)
            else:
                yield full_name, val

    def items(self, prefix: str = '') -> Iterator[tuple[str, object]]:
        """
        Yield (name, value) pairs for every leaf in config.data,
        where name is the full dotted path to the leaf.
        If prefix is supplied, only yield items under that subtree.
        Raises KeyError if prefix is supplied but not found.
        """
        if prefix:
            subtree = self.get_by_name(prefix)
            if not isinstance(subtree, dict):
                yield prefix, subtree
                return
            yield from self._traverse(subtree, prefix)
        else:
            yield from self._traverse(self.data)

    # ------------------------------------------------------------------
    # Command line parsing
    # ------------------------------------------------------------------

    def add_cli_arg(self, *flags: str,
                    name: str | None = None,
                    **kwargs) -> None:
        """
        Add a CLI argument to the internal parser.

        If name is supplied, the argument is mapped to that config item
        using dotted name notation, e.g. name='scope.time_per_div'.
        merge_cli() will apply its value to the corresponding location
        in config.data.  The type of the argument is inferred from the
        current value at that name unless overridden by a 'type' kwarg.
        The name may refer to any depth in the config tree.

        If name is omitted, the argument is added to the parser but not
        mapped to any config item.  It will appear in the args object
        returned by parse_cli() and is available for the caller to use
        directly.

        Positional arguments are supported, but cannot be mapped to
        config data.  If it is necessary to save a positional argument
        value to config data, extract the value from the Namespace
        returned by parse_cli() and use set_by_name() to store it.

        flags and all other kwargs are passed through to
        parser.add_argument(), supporting the full argparse API including
        action, choices, nargs, required, metavar, etc.

        Examples:
            config.add_cli_arg('-p', '--port', name='port.port')
            config.add_cli_arg('--time-per-div', name='scope.time_per_div')
            config.add_cli_arg('--verbose', action='store_true')
            config.add_cli_arg('--cfg', help="path to config file")
        """
        if name is not None:
            # mapped arg: validate name and infer type
            try:
                current_val = self.get_by_name(name)
            except KeyError:
                raise KeyError(f"config name '{name}' not found; "
                               f"call set_by_name() before add_cli_arg()")
            if isinstance(current_val, dict):
                raise ValueError(f"config name '{name}' refers to a dict, "
                                 f"not a leaf value; CLI args must map to leaf values")
            dest = name.replace('.', '__')
            # infer type from current value unless caller supplied one;
            # bool must be checked before int since bool is a subclass of int
            if 'type' not in kwargs and 'action' not in kwargs:
                if isinstance(current_val, bool):
                    kwargs['type'] = lambda s: s.lower() not in ('0', 'false', 'no', 'off')
                elif isinstance(current_val, int):
                    kwargs['type'] = int
                elif isinstance(current_val, float):
                    kwargs['type'] = float
                else:
                    kwargs['type'] = str
            self._parser.add_argument(*flags, dest=dest, default=None, **kwargs)
            self._cli_map.append((dest, name))
        else:
            # unmapped arg: pass through to argparse unchanged
            self._parser.add_argument(*flags, **kwargs)

    def parse_cli(self, args: list[str] | None = None) -> argparse.Namespace:
        """
        Parse the command line and save the result for merge_cli().
        Returns the args namespace for immediate use by the caller,
        e.g. to retrieve a config file path before calling load_file().
        If args is provided, it is parsed instead of sys.argv; this is
        useful for testing.
        """
        self._args = self._parser.parse_args(args)
        return self._args

    def merge_cli(self) -> None:
        """
        Apply saved CLI values to config.data.
        Only mapped args (those registered with a name) are merged;
        unmapped args are ignored.
        parse_cli() must be called before merge_cli().
        CLI values take precedence over any values loaded from files.
        """
        if self._args is None:
            raise RuntimeError("parse_cli() must be called before merge_cli()")
        for dest, name in self._cli_map:
            val = getattr(self._args, dest, None)
            if val is not None:
                self.set_by_name(name, val)

    # ------------------------------------------------------------------
    # Load and save
    # ------------------------------------------------------------------

    def load_file(self, path: str | Path) -> bool:
        """
        Read a config file and merge its contents into config.data.
        Traverses the file's JSON tree and calls set_by_name() for each
        leaf, so type checking and default preservation apply automatically.
        May be called more than once; later calls take precedence over
        earlier ones for overlapping keys.
        Reports an error and returns False if the file is not found or
        cannot be parsed.  Returns True on success.
        """
        path = Path(path)
        ctx.push(source=str(path))
        ok = True
        try:
            with open(path, 'r', encoding='utf-8') as f:
                filedata = json.load(f)
        except FileNotFoundError:
            ctx.error(f"config file {path.as_posix()!r} not found",
                      source=OMIT)
            ok = False
        except json.JSONDecodeError as e:
            ctx.error(f"JSON parse error: {e.msg}", lineno=e.lineno, column=e.colno)
            ok = False
        except OSError as e:
            ctx.error(f"could not read config file: {e}", lineno=OMIT, column=OMIT)
            ok = False
        if ok:
            for name, value in self._traverse(filedata):
                self.set_by_name(name, value)
        ctx.summarize()
        ctx.pop()
        return ok

    def save_file(self, path: str | Path) -> None:
        """
        Write all of config.data to the given path as JSON.
        The entire contents of config.data are written; no filtering
        is applied.
        """
        path = Path(path)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
        except OSError as e:
            print(f"error writing config file {path.as_posix()!r}: {e}",
                  file=sys.stderr)
