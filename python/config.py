# config.py
# Provides Config and ConfigView for managing configuration
# data across GUI and command-line tools, reading from and/or
# writing to a shared JSON config file.

from __future__ import annotations
from typing import NamedTuple, Any
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Iterator

from parse_common import ctx, OMIT


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# we store only types that are lossless over a JSON round trip
_LEAF_TYPES = (str, int, float, bool)

class Config:
    """
    Manages configuration data.

    Configuration data is stored in a single nested dict (config._data)
    and accessed using paths as in a filesystem tree.  Paths not ending
    with '/' are "leaf nodes" containing config data items.  All data
    items must be of a type in _LEAF_TYPES defined above.  Paths
    ending with '/' are 'subdir' nodes that can be used to add
    structure to the config data.

    When accessing a Config object, all paths must be absolute, with
    a leading '/'.  The ConfigView class (defined below) is a wrapper
    that allows relative paths; this lets consumer classes register
    their own items while the application controls the overall data
    hierarchy.

    Consumer classes register their keys by calling register() with
    default values during initialization.  This establishes both the
    existence and expected type of each key, as well as creating any
    subdirectory nodes needed to reach the item.

    Data items are accessed using get() and set() methods.

    Registered data items can be loaded from files or the command line,
    and saved to files.  load_file() may be called one or more times
    to merge file contents into config._data; later calls take
    precedence over earlier ones for overlapping keys.

    merge_cli() applies command line values; if called last, it gives
    them highest precedence.

    See the end of this file for typical usage.
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
        If a path contains '//', the function resets to the absolute
        root at that point; this allows specifying an absolute path
        even when working with a ConfigView which normally prepends
        a base path.
        This method only looks at the name as a string; it does not
        check any actual data structure (see _resolve_path() for that).
        Raises ValueError if path is not absolute or uses '..' when
        at the root.
        """
        if not path.startswith('/'):
            raise ValueError(f"'{path}' is not absolute")
        parts = path.split('/')
        last = parts[-1]
        match last:
            case '':
                # original path ended with '/'
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
                    # '//' means reset to root
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

    def register(self, path: str, value: Any) -> None:
        """
        Adds a leaf item to the data structure at 'path', with type
        and default value as specified by 'value'.  If the item already
        exists, its value will not be changed, but a type mismatch will
        raise TypeError.
        Raises KeyError if the path ends in '/' or any intermediate
        node on the path already exists as a leaf.
        Raises TypeError if the type of 'value' is not in _LEAF_TYPES.
        """
        result = self._flatten_path(path)
        if type(value) not in _LEAF_TYPES:
            allowed = ', '.join(t.__name__ for t in _LEAF_TYPES)
            raise TypeError(f"Cannot register '{result.flat_path}': bad type "
                            f"'{type(value).__name__}' (must be one of: {allowed})")
        if not result.is_leaf:
            raise KeyError(f"Cannot register '{result.flat_path}'; not a leaf")
        node = self._data
        # traverse to the parent of the leaf, creating dicts as needed
        for name in result.names[:-1]:
            if name not in node:
                # create new subdir
                node[name] = {}
            elif not isinstance(node[name], dict):
                raise KeyError(f"'{result.flat_path}': '{name}' is already set as a leaf value; "
                    f"cannot use it as an intermediate node"
                )
            node = node[name]
        leaf = result.names[-1]
        if leaf not in node:
            # create the new item
            node[leaf] = value
        else:
            # already exists: don't change value, but raise if types don't match
            if type(value) is not type(node[leaf]):
                raise TypeError(f"cannot re-register '{result.flat_path}'; type mismatch")

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

    def set(self, path: str, value: Any) -> None:
        """
        Sets the leaf item at 'path' to 'value'.
        Raises KeyError if the path ends with '/' or the item is not
        registered.
        Raises ValueError if the type of 'value' does not match the
        registered type.  Exception: if the registered type is float
        and 'value' is int, 'value' is converted to float.
        """
        result = self._resolve_path(path)
        if not result.is_leaf:
            raise KeyError(f"Cannot set '{result.flat_path}'; not a leaf")
        existing = result.value
        if type(existing) is float and type(value) is int:
            try:
                value = float(value)
            except OverflowError:
                raise ValueError(f"'{result.flat_path}': integer too large "
                                 f"for a float") from None
        if type(value) is type(existing):
            result.subdir[result.key] = value
        else:
            raise ValueError(
                f"'{result.flat_path}' has wrong type "
                f"(expected {type(existing).__name__}, "
                f"got {type(value).__name__})"
            )

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
        Yield (name, value) pairs for every leaf at node 'path' (and below,
        if 'recurse' is true), where name is the full path to the leaf.
        Raises KeyError if 'path' describes a leaf or does not exist
        in the tree.
        """
        result = self._resolve_path(path)
        if result.is_leaf:
            raise KeyError(f"Cannot iterate '{result.flat_path}'; it is a leaf")
        prefix = result.flat_path
        subdir = result.value
        for key, val in subdir.items():
            if not isinstance(val, dict):
                yield f"{prefix}{key}", val
            elif recurse:
                yield from self._recurse_items(val, f"{prefix}{key}/")

    def list_all(self, path: str = '/') -> None:
        """
        Print all items in the Config as name: value for leaves,
        name only for subdirs.
        """
        for name in self.names(path, True):
            if name.endswith('/'):
                print(f"{name}")
            else:
                print(f"{name}: {self.get(name)}")

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
        Yield name for every leaf or subdir at 'path' (and below, if
        'recurse' is true), where name is the full path from the root.
        Raises KeyError if 'path' describes a leaf or does not exist
        in the tree.
        """
        result = self._resolve_path(path)
        if result.is_leaf:
            raise KeyError(f"Cannot iterate '{result.flat_path}'; it is a leaf")
        prefix = result.flat_path
        subdir = result.value
        for key, val in subdir.items():
            if isinstance(val, dict):
                yield f"{prefix}{key}/"
                if recurse:
                    yield from self._recurse_names(val, f"{prefix}{key}/")
            else:
                yield f"{prefix}{key}"

    def list_names(self, path: str = '/') -> None:
        """
        Print the names of all items in the Config.
        """
        for name in self.names(path, True):
            print(f"{name}")

    def add_cli_arg(self, *flags: str,
                    name: str | None = None,
                    **kwargs) -> None:
        """
        Add a CLI argument to the internal parser.

        If name is supplied, the argument is mapped to that config
        item using path notation, e.g. name='/scope/time_per_div'.
        merge_cli() will apply its value to the corresponding location
        in config._data.  The type of the argument is inferred from the
        current value at that name unless overridden by a 'type' kwarg.
        The name may refer to any depth in the config tree.

        If name is omitted, the argument is added to the parser but not
        mapped to any config item.  It will appear in the args object
        returned by parse_cli() and is available for the caller to use
        directly.

        Positional arguments are supported, and can be mapped to
        config data.

        For mapped arguments the parsed value must be a single value
        of the item's type, so options that produce lists (such as
        nargs greater than 1 or action='append') can't be used.

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
            # infer type from current value unless caller supplied one;
            # bool must be checked before int since bool is a subclass of int
            if 'type' not in kwargs and 'action' not in kwargs:
                if isinstance(current_val, bool):
                    # bool is subset of int, but needs special handling,
                    # including this dedicated parse function:
                    def _parse_bool(s: str) -> bool:
                        match s.lower():
                            case '1' | 'true' | 'yes' | 'on':
                                return True
                            case '0' | 'false' | 'no' | 'off':
                                return False
                            case _:
                                raise argparse.ArgumentTypeError(
                                    f"invalid boolean value: {s!r}"
                                )
                    kwargs['type'] = _parse_bool
                elif isinstance(current_val, int):
                    kwargs['type'] = int
                elif isinstance(current_val, float):
                    kwargs['type'] = float
                elif isinstance(current_val, str):
                    kwargs['type'] = str
                else:
                    raise TypeError(f"'{name}': unsupported type {type(current_val).__name__}")
            action = self._parser.add_argument(*flags, default=None, **kwargs)
            self._cli_map.append((action.dest, name))
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
        Apply saved CLI values to config._data.
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

    def load_file(self, path: str | Path) -> bool:
        """
        Read a config file and merge its contents into config._data.
        Traverses the file's JSON tree and calls set() for each leaf
        so type checking and default preservation apply automatically.
        This means that keys contained in the file but not registered
        by the application will be ignored with a warning.
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
        except Exception as e:
            ctx.error(f"could not load config file: {type(e).__name__}: {e}",
                      lineno=OMIT, column=OMIT)
            ok = False
        if ok and not isinstance(filedata, dict):
            ctx.error("top level of config file must be a JSON object",
                      lineno=OMIT, column=OMIT)
            ok = False
        if ok:
            for name, value in self._recurse_items(filedata, '/'):
                try:
                    self.set(name, value)
                except ( KeyError, ValueError ) as e:
                    ctx.warning(f"{e.args[0]}, ignoring", lineno=OMIT, column=OMIT)
        ctx.summarize()
        ctx.pop()
        return ok

    def save_file(self, path: str | Path) -> None:
        """
        Write all of config._data to the given path as JSON.
        The entire contents of config._data are written; no filtering
        is applied.
        Works by saving to a temp file first, so if an error occurs any
        old config data is not lost.
        The directory containing the target file must already exist.
        """
        target = Path(path).resolve()
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())   # make sure data is on disk before the swap
            os.replace(tmp, target)    # atomic swap
        except OSError as e:
            print(f"error writing config file {target.as_posix()!r}: {e}",
                  file=sys.stderr)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

# ------------------------------------------------------------------

class ConfigView:
    """
    ConfigView provides a "view" of a Config object that is relative
    to the location specified by 'path'.  Allows objects to manage
    their config data without worrying about where that data lives
    in the overall tree.
    When working with a ConfigView, the default relative path syntax
    can be overridden by applying a leading '/' to any path; when
    the base path is concatenated, that will result in '//' which
    will reset the path resolver to the absolute root.
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

    def register(self, path: str, value) -> None:
        self.root.register(f"{self.cwd}{path}", value)

    def is_registered(self, path: str) -> bool:
        return self.root.is_registered(f"{self.cwd}{path}")

    def get(self, path: str) -> Any:
        return self.root.get(f"{self.cwd}{path}")

    def set(self, path: str, value) -> None:
        self.root.set(f"{self.cwd}{path}", value)

# ------------------------------------------------------------------
#
#  SAMPLE CODE
#
# ------------------------------------------------------------------

if __name__ == '__main__':

    class ComPort:
        """
        Sample class for a communication port.
        """
        def __init__(self, config: ConfigView):
            self.config = config
            # read and use config data
            self.port = config.get("port")
            self.baud = config.get("baud")

        @staticmethod
        def register_config(config: ConfigView):
            """
            Register config data items needed by a ComPort
            """
            config.register("port", "")
            config.register("baud", 9600)

        def change_baud(self, new_baud: int):
            """
            Sample of modifying a config value within a class
            """
            self.baud = new_baud
            # store new value in config data
            self.config.set("baud", self.baud)

    class Meter:
        """
        Sample class showing how ConfigViews can be nested.
        One Meter object has four Input objects, each with
        its own configuration data.
        """
        def __init__(self, config: ConfigView):
            self.config = config
            # register Meter and Input config data, if not already done
            self.register_config(self.config)
            # create the Input objects
            self.input_objects = []
            for n in range(4):
                input_view = ConfigView(self.config, f"input{n}/")
                self.input_objects.append(Input(input_view))

        @staticmethod
        def register_config(config: ConfigView):
            # register this object's config data
            config.register("font_size", 10)
            # register subsidiary object(s) config data
            for n in range(4):
                Input.register_config(ConfigView(config, f"input{n}/"))

    class Input:
        """
        Sample class for a single Input, to be nested
        within a Meter object.
        """
        def __init__(self, config: ConfigView):
            self.config = config
            # make sure config data for this Input is registered
            self.register_config(self.config)
            # read and use config data
            self.units = config.get("units")

        @staticmethod
        def register_config(config: ConfigView):
            """
            Register config data items needed by an Input
            """
            config.register("label", "a string")
            config.register("gain", 17)
            config.register("units", "volts")

        def raise_gain(self):
            """
            Sample of modifying a config value within a class
            """
            # get present value from config data
            gain = self.config.get("gain")
            # change it
            gain += 1
            # store new value in config data
            self.config.set("gain", gain)


    def main():
        """
        GUI classes create widgets during their __init__() methods,
        and often need config data to do that.  So this application
        registers config data for all classes that it wants to use
        before creating the class instances.
        Then it reads the config file and merges any CLI values
        into the Config data before it actually creates the widgets.
        """
        print(f"testing config")
        app_config = Config()
        print(f"After creation:\n")
        app_config.list_all()

        # register root-level config items
        app_config.register("/root_foo", 42)
        app_config.register("/root_bar", 33)
        # register config items for a Meter object and its children
        meter_config = ConfigView(app_config, "meter/")
        Meter.register_config(meter_config)
        # register config items for a ComPort
        comport_config = ConfigView(app_config, "port/")
        ComPort.register_config(comport_config)

        print(f"After registering:\n")
        app_config.list_all()

        # set up command line arguments
        # --cfg is not mapped to a config name, it is only used to find the config file
        app_config.add_cli_arg('--cfg', help="path to config file")
        # --font-size is mapped to a config value
        app_config.add_cli_arg('--font-size', name='/meter/font_size', help="font size for meter widget")
        # --com-port and --baud are mapped to config values
        app_config.add_cli_arg('--com-port', name='/port/port', help="COM port for target connection")
        app_config.add_cli_arg('--baud', name='/port/baud', help="baud rate for target connection")
        # --verbose is not mapped to config data, used only by the main program
        app_config.add_cli_arg('--verbose', action='store_true', help="verbose output")

        # parse CLI first so we can use --cfg to find the config file
        args = app_config.parse_cli()

        # config file is 'config.json' unless --cfg was supplied on command line
        cfg_path = Path(args.cfg) if args.cfg else Path('config.json')
        if cfg_path.exists():
            # get values from config file
            print(f"\nReading from config file '{cfg_path}'...")
            app_config.load_file(cfg_path)

        print(f"\nAfter file load:\n")
        app_config.list_all()

        # get command line last so it supersedes defaults and file values
        app_config.merge_cli()

        print(f"\nAfter command line:\n")
        app_config.list_all()

        # create widgets
        meter = Meter(meter_config)
        comport = ComPort(comport_config)

        print(f"\nAfter widget creation:\n")
        app_config.list_all()

        # program execution - typically the user would invoke things
        # but we are faking it here...
        meter.input_objects[2].raise_gain()
        meter.input_objects[2].raise_gain()
        meter.input_objects[1].raise_gain()
        meter.input_objects[2].raise_gain()
        comport.change_baud(115200)

        print(f"\nAfter execution:\n")
        app_config.list_all()

        print(f"saving config to '{cfg_path}'")
        app_config.save_file(cfg_path)

        print(f"done")

    main()
