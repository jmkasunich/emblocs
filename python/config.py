# config.py
# Provides Config for managing tool configuration data across
# GUI and command-line tools, reading from and writing to a
# shared JSON config file.

from __future__ import annotations
from typing import NamedTuple, Any
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
    Manages configuration data.

    Configuration data is stored in a single nested dict (config._data)
    and accessed using paths as in a filesystem tree.  Paths not ending
    with '/' are "leaf nodes" containing config data items.  Paths
    ending with '/' are 'subdir' nodes that can be used to add
    structure to the config data.

    When accessing a Config object, all paths must be absolute, with
    a leading '/'.  The ConfigView class (defined below) is a wrapper
    that allows relative paths; this lets consumer classes register
    their own items while the application controls the overall data
    heirarchy.

    Consumer classes register their keys by calling register() with
    default values during initialization.  This establishes both the
    existence and expected type of each key, as well as creating any
    subdirectory nodes needed to reach the item.

    Data items can be loaded from files or the command line, and
    saved to files.  load_file() may be called one or more times
    to merge file contents into config._data; later calls take
    precedence over earlier ones for overlapping keys.

    merge_cli() applies command line values; if called last, it gives
    them highest precedence.

    Typical usage:

        config = Config()

        # register keys with defaults
        config.register('/paths/bloc_search_paths', [])
        config.register('/text/font_size', 12)

        # set up CLI args
        # --cfg is not mapped to a config name, used to find the config file
        config.add_cli_arg('--cfg', help="path to config file")
        # --font-size is mapped to a config value
        config.add_cli_arg('--font-size', name='/text/font_size', help="font size for text window")
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

        size = config.get("/text/font_size")
        size += 1
        config.set("/text/font_size", size)

        config.save_file(cfg_path)

    Typical usage in a consumer class:

        class SerPort:
            @staticmethod
            def register_config(config):
                config.register('/port/port', '')
                config.register('/port/baud', '115.2K')
                config.add_cli_arg('-p', '--port', name='/port/port',
                                   help="serial port name")
                config.add_cli_arg('-b', '--baud', name='/port/baud',
                                   help="baud rate")

            def __init__(self, config):
                self.port = config.get('/port/port')
                self.baud = config.get('/port/baud')
    """

    def __init__(self) -> None:
        self._data:    dict                       = {}
        self._cli_map: list[tuple[str, str]]      = []    # (dest, name) for mapped args
        self._args:    argparse.Namespace | None  = None  # saved by parse_cli()
        self._parser:  argparse.ArgumentParser    = argparse.ArgumentParser()

    class _flatten_path_retval(NamedTuple):
        flat_path: str
        names: list[str]
        is_leaf: bool

    def _flatten_path(self, path: str) -> _flatten_path_retval:
        """
        Helper function - accepts a path and resolves all '.' & '..'
        entries, returning the flat path, a list of the names in the
        path, and whether the path refers to a leaf or a subdir.
        Subdir paths must end in '/', leaf paths must not.
        Raises ValueError if path is not absolute or uses '..' when
        at the root.
        """
        if not path.startswith('/'):
            raise ValueError(f"'{path}' is not absolute")
        parts = path.split('/')
        last = parts[-1]
        match last:
            case '':
                is_leaf = False
                parts.pop()
            case '..' | '.':
                is_leaf = False
            case _:
                is_leaf = True
        names = []
        for part in parts:
            match part:
                case '':
                    names = []
                case '..':
                    if names:
                        names.pop()
                    else:
                        raise ValueError(f"'{path}' contains '..' at root")

                case '.':
                    pass
                case _:
                    names.append(part)
        flat_path = f"/{'/'.join(names)}"
        if not is_leaf and not flat_path.endswith('/'):
            flat_path = f"{flat_path}/"
        return self._flatten_path_retval(flat_path, names, is_leaf)

    def flat_path(self, path:str) -> str:
        """
        Returns a path with all '.' and '..' entries resolved.
        Raises ValueError if path is not absolute or uses '..' when
        at the root.
        """
        result = self._flatten_path(path)
        return result.flat_path

    class _resolve_path_retval(NamedTuple):
        flat_path: str
        is_leaf: bool
        subdir: dict
        key: str
        value: Any

    def _resolve_path(self, path: str) -> _resolve_path_retval:
        """
        Helper function - accepts a path and searches the data structure
        for it.  Returns information about the named object.
        Subdir paths must end in '/', leaf paths must not.
        Raises KeyError if the object does not exist, or if the object
        is leaf but the path expects subdir or vice-versa.
        """
        result = self._flatten_path(path)
        # now see if there is a match in the nested dict
        data = self._data
        subdir = {}
        name = ''
        msg_path = []
        for name in result.names:
            if not isinstance(data, dict):
                raise KeyError(f"config item '/{'/'.join(msg_path)}/' is not a dict")
            subdir = data
            msg_path.append(name)
            if name not in subdir:
                raise KeyError(f"config item '/{'/'.join(msg_path)}' not found")
            data = subdir[name]
        if result.is_leaf:
            if isinstance(data, dict):
                raise KeyError(f"config item '/{'/'.join(msg_path)}' is not a leaf")
        else:
            if not isinstance(data, dict):
                raise KeyError(f"config item '/{'/'.join(msg_path)}' is not a dict")
        return self._resolve_path_retval(result.flat_path, result.is_leaf, subdir, name, data)

    def register(self, path: str, value: Any):
        """
        Adds a leaf item to the data structure at 'path', with type
        and default value as specified by 'value'.
        Raises KeyError if the path ends in '/', the object already
        exists, or any intermediate node on the path already exists
        as a leaf.
        """
        result = self._flatten_path(path)
        if not result.is_leaf:
            raise KeyError(f"Cannot register '{result.flat_path}'; not a leaf")
        node = self._data
        # traverse to the parent of the leaf, creating dicts as needed
        for name in result.names[:-1]:
            if name not in node:
                node[name] = {}
            elif not isinstance(node[name], dict):
                raise KeyError(f"'{result.flat_path}': '{name}' is already set as a leaf value; "
                    f"cannot use it as an intermediate node"
                )
            node = node[name]
        leaf = result.names[-1]
        if leaf in node:
            raise KeyError(f"'{result.flat_path}' is already registered")
        node[leaf] = value

    def is_registered(self, path: str) -> bool:
        """
        Returns true if a leaf node exists at 'path'
        """
        try:
            result = self._resolve_path(path)
            if not result.is_leaf:
                return False
            return True
        except KeyError:
            return False

    def get(self, path: str) -> Any:
        """
        Returns the data value of the leaf item at 'path'.
        Raises KeyError if the path ends with '/' or the item is not
        registered.
        """
        result = self._resolve_path(path)
        if not result.is_leaf:
            raise KeyError(f"Cannot get '{result.flat_path}'; not a leaf")
        return result.value

    def set(self, path: str, value: Any):
        """
        Sets the leaf item at 'path' to 'value'.
        Raises KeyError if the path ends with '/' or the item is not
        registered.
        Raises ValueError if the type of 'value' does not match the
        registered type.
        """
        result = self._resolve_path(path)
        if not result.is_leaf:
            raise KeyError(f"Cannot set '{result.flat_path}'; not a leaf")
        existing = result.value
        type_ok = (
            isinstance(existing, bool) and isinstance(value, bool)
        ) or (
            not isinstance(existing, bool) and
            type(value) is type(existing)
        )
        if type_ok:
            result.subdir[result.key] = value
        else:
            raise ValueError(
                f"'{result.flat_path}' has wrong type "
                f"(expected {type(existing).__name__}, "
                f"got {type(value).__name__}); "
            )

    # ------------------------------------------------------------------
    # Iterators
    # ------------------------------------------------------------------

    def _recurse_items(self, d: dict, path: str) -> Iterator[tuple[str, object]]:
        """
        Helper for items() - recursively yields (name, value) pairs
        for every leaf in d, where name is the full path to the leaf.
        Dicts are traversed; all other values are treated as leaves.
        """
        for key, val in d.items():
            if isinstance(val, dict):
                yield from self._recurse_items(val, f"{path}{key}/")
            else:
                yield f"{path}{key}", val

    def items(self, path: str = '/', recurse: bool = False ) -> Iterator[tuple[str, object]]:
        """
        Yield (name, value) pairs for every leaf at node 'path' (and
        below, if 'recurse' is true), where name is the full path
        to the leaf.
        Raises KeyError if 'path' describes a leaf or does not exist
        in the tree.
        """
        result = self._resolve_path(path)
        if result.is_leaf:
            raise KeyError(f"Cannot iterate '{result.flat_path}'; it is a leaf")
        subdir = result.value
        for key, val in subdir.items():
            if not isinstance(val, dict):
                yield f"{path}{key}", val
            elif recurse:
                yield from self._recurse_items(val, f"{path}{key}/")

    def _recurse_names(self, d: dict, path: str) -> Iterator[str]:
        """
        Helper for names() - recursively yields name for every leaf
        or subdir in d, where name is the full path to the node.
        Dicts are traversed; all other values are treated as leaves.
        """
        for key, val in d.items():
            if isinstance(val, dict):
                yield f"{path}{key}/"
                yield from self._recurse_names(val, f"{path}{key}/")
            else:
                yield f"{path}{key}"

    def names(self, path: str = '/', recurse: bool = False ) -> Iterator[str]:
        """
        Yield name for every leaf or subdir at 'path' (and
        below, if 'recurse' is true), where name is the full path
        to the leaf.
        Raises KeyError if 'path' describes a leaf or does not exist
        in the tree.
        """
        result = self._resolve_path(path)
        if result.is_leaf:
            raise KeyError(f"Cannot iterate '{result.flat_path}'; it is a leaf")
        subdir = result.value
        for key, val in subdir.items():
            if isinstance(val, dict):
                yield f"{path}{key}/"
                if recurse:
                    yield from self._recurse_names(val, f"{path}{key}/")
            else:
                yield f"{path}{key}"

    # ------------------------------------------------------------------
    # Command line parsing
    # ------------------------------------------------------------------

    def add_cli_arg(self, *flags: str,
                    name: str | None = None,
                    **kwargs) -> None:
        """
        Add a CLI argument to the internal parser.

        If name is supplied, the argument is mapped to that config
        item using path notation, e.g. name='/scope/time_per_div'.
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
        returned by parse_cli() and use set() to store it.

        flags and all other kwargs are passed through to
        parser.add_argument(), supporting the full argparse API including
        action, choices, nargs, required, metavar, etc.

        Examples:
            config.add_cli_arg('-p', '--port', name='/port/port')
            config.add_cli_arg('--time-per-div', name='/scope/time_per_div')
            config.add_cli_arg('--verbose', action='store_true')
            config.add_cli_arg('--cfg', help="path to config file")
        """
        if name is not None:
            # mapped arg: validate name and infer type
            try:
                result = self._resolve_path(name)
            except KeyError:
                raise KeyError(f"config item '{name}' not found; "
                               f"call register() before add_cli_arg()")
            if not result.is_leaf:
                raise ValueError(f"config name '{name}' is not a leaf value, "
                                 f"cannot be mapped to a CLI arg")
            current_val = result.value
            dest = name.replace('/', '__')
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
                self.set(name, val)

    # ------------------------------------------------------------------
    # Load and save
    # ------------------------------------------------------------------

    def load_file(self, path: str | Path) -> bool:
        """
        Read a config file and merge its contents into config.data.
        Traverses the file's JSON tree and calls set() for each leaf
        so type checking and default preservation apply automatically.
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
            for name, value in self._recurse_items(filedata, '/'):
                try:
                    self.set(name, value)
                except KeyError as e:
                    ctx.warning(f"{e}, ignoring", lineno=OMIT, column=OMIT)
                except ValueError as e:
                    ctx.warning(f"{e}, ignoring", lineno=OMIT, column=OMIT)
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
                json.dump(self._data, f, indent=4)
        except OSError as e:
            print(f"error writing config file {path.as_posix()!r}: {e}",
                  file=sys.stderr)


##############################################################

class ConfigView:
    """
    ConfigView provides a "view" of a Config object that is relative
    to the location specified by 'path'.  Allows objects to manage
    their config data without worrying about where that data lives
    in the ovarall tree.
    """
    def __init__(self, parent: ConfigView | Config, path: str):
        if not path.endswith('/'):
            path = f"{path}/"
        if isinstance(parent, ConfigView):
            self.root = parent.root
            path = f"{parent.cwd}{path}"
        elif isinstance(parent, Config):
            self.root = parent
            if not path.startswith('/'):
                path = f"/{path}"
        else:
            raise TypeError(f"parent must be ConfigView or Config, got {type(parent)!r}")
        self.cwd = self.root.flat_path(path)

    def register(self, path: str, value):
        self.root.register(f"{self.cwd}{path}", value)

    def is_registered(self, path: str) -> bool:
        return self.root.is_registered(f"{self.cwd}{path}")

    def get(self, path: str):
        return self.root.get(f"{self.cwd}{path}")

    def set(self, path: str, value):
        self.root.set(f"{self.cwd}{path}", value)


############################################################################
#  SAMPLE CODE
#
# class Channels:
#     def __init__(self, config: ConfigView):
#         self.config = config
#         self.num_chan = config.get("number_of_channels")
#         self.channel_widgets = []
#         for n in range(self.num_chan):
#             self.channel_widgets.apppend(Channel(ConfigView(self.config, f"chan{n}/")))
#
#     @staticmethod
#     def register_config_data(config: ConfigView, num_chan: int):
#         config.register("number_of_channels", num_chan)
#         config.register("foo", "a string")
#         for n in range(num_chan):
#             Channel.register_config_data(ConfigView(config, f"chan{n}/"))
#
#
# class Channel:
#     def __init__(self, config: ConfigView):
#         self.config = config
#         self.units = config.get("units")
#
#     @staticmethod
#     def register_config_data(config: ConfigView):
#         config.register("label", "a string")
#         config.register("gain", 17)
#         config.register("units", "volts")
#
#     def raise_gain(self):
#         # get present value from config data
#         gain = self.config.get("gain")
#         # change it
#         gain += 1
#         # store new value in config data
#         self.config.set("gain", gain)
#
#
# def main():
#     app_config = Config()
#     app_config.register("root_foo", 42)
#     app_config.register("root_bar", 33)
#     Channels.register_config_data(ConfigView(app_config, "channels/"), 4)
#
#     app_config.load_file("my_config_file.json")
#
#     chans_widget = Channels(ConfigView(app_config, "channels/"))

