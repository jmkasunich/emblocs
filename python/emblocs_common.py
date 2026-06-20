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

from parse_common import ctx, OMIT


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config:
    """
    Manages configuration data for EMBLOCS tools.

    All tools share a single JSON config file.  Each consumer class
    (or the tool's main script) registers sections before load() is
    called.  Two kinds of sections are supported:

    Owned sections are registered by exactly one consumer class.  On
    save(), only the registered keys are written back; unrecognized keys
    from the file are dropped.  This provides automatic housekeeping as
    key names change over time.

    Shared sections are registered by the tool's main script and may be
    read by any consumer.  On save(), all keys that were present in the
    file are preserved, and registered keys are updated with current
    values.  Unrecognized keys from the file are never dropped.  This
    allows tools that register different subsets of a shared section to
    coexist without clobbering each other's data.

    Typical usage in a tool's main script:

        config = Config()
        config.register_shared('app', {'geometry': ''})
        config.register_shared('paths', {'bloc_search_paths': []})
        SerPort.register_config(config)
        Console.register_config(config)
        parser = config.base_arg_parser(description="EMBLOCS GUI tool")
        config.add_cli_arg('-p', '--port', help="serial port name",
                           section='port', key='port')
        args = parser.parse_args()
        config.load(args)

    Typical usage in a consumer class:

        class SerPort:
            _CONFIG_SECTION = 'port'
            _CONFIG_DEFAULTS = {
                'port': '',
                'baud': '115.2K',
            }

            @classmethod
            def register_config(cls, config):
                config.register_owned(cls._CONFIG_SECTION, cls._CONFIG_DEFAULTS)

            def __init__(self, config):
                self.cfg = config.section('port')
                # access as self.cfg['port'], self.cfg['baud'], etc.
    """

    def __init__(self,
                 project_cfg: str | Path,
                 template_cfg: str | Path | None = None ) -> None:
        self._project_cfg:  Path = Path(project_cfg)
        self._template_cfg: Path | None = Path(template_cfg) if template_cfg is not None else None
        self._owned:       dict[str, dict]  = {}    # section -> defaults
        self._shared:      dict[str, dict]  = {}    # section -> defaults
        self._filedata:    dict             = {}    # raw JSON as read, for pass-through
        self._cli_map:     list[tuple]      = []    # (dest, section, key) for CLI overrides
        self._parser:      argparse.ArgumentParser | None = None
        self.data:         dict[str, dict]  = {}    # live working copy of all sections

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_owned(self, section: str, defaults: dict) -> None:
        """
        Register an owned section with its default values.
        Must be called before load().
        The section name must not already be registered as shared.
        """
        if section in self._shared:
            raise ValueError(f"section '{section}' is already registered as shared")
        self._owned[section] = dict(defaults)
        self.data[section] = dict(defaults)

    def register_shared(self, section: str, defaults: dict) -> None:
        """
        Register a shared section with its default values.
        Must be called before load().
        The section name must not already be registered as owned.
        """
        if section in self._owned:
            raise ValueError(f"section '{section}' is already registered as owned")
        self._shared[section] = dict(defaults)
        self.data[section] = dict(defaults)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def section(self, name: str) -> dict:
        """
        Return a live reference to a registered section.
        Raises KeyError if the section has not been registered.
        Consumer classes that own a section may read and write through
        this reference.  Consumer classes that only read a shared section
        should treat the returned dict as read-only by convention.
        """
        if name not in self.data:
            raise KeyError(f"config section '{name}' has not been registered")
        return self.data[name]

    # ------------------------------------------------------------------
    # CLI argument parser
    # ------------------------------------------------------------------

    def base_arg_parser(self, **kwargs) -> argparse.ArgumentParser:
        """
        Create, store, and return an ArgumentParser.
        The caller may add additional arguments to the returned parser before
        calling parse_args().  Any keyword arguments are forwarded to
        ArgumentParser(), e.g. description="my tool".
        Must be called before add_cli_arg().
        """
        self._parser = argparse.ArgumentParser(**kwargs)
        return self._parser

    def add_cli_arg(self, *flags: str,
                    section: str,
                    key: str,
                    help: str = '') -> None:
        """
        Add a CLI argument to the parser and record its mapping to a config key.
        base_arg_parser() must be called before this method.
        The type of the argument is inferred from the registered default value
        for section/key.  load() will apply any non-None CLI value to the
        config data automatically after merging the file.

        flags are passed directly to parser.add_argument(), so both short
        and long forms are supported:
            config.add_cli_arg('-p', '--port', section='port', key='port')
            config.add_cli_arg('--port', section='port', key='port')

        The dest name in the resulting args namespace is derived from section
        and key as '<section>__<key>', avoiding any ambiguity from argparse's
        own dest-derivation rules.

        section and key must already be registered before calling this method.
        """
        if self._parser is None:
            raise RuntimeError("base_arg_parser() must be called before add_cli_arg()")
        if section not in self.data:
            raise KeyError(f"config section '{section}' has not been registered")
        if key not in self.data[section]:
            raise KeyError(f"key '{key}' not found in config section '{section}'")
        dest = f"{section}__{key}"
        default_val = self.data[section][key]
        # infer type from default; bool must be checked before int since
        # bool is a subclass of int in Python
        if isinstance(default_val, bool):
            arg_type = lambda s: s.lower() not in ('0', 'false', 'no', 'off')
        elif isinstance(default_val, int):
            arg_type = int
        elif isinstance(default_val, float):
            arg_type = float
        elif isinstance(default_val, list):
            arg_type = str   # individual list items supplied as strings on CLI
        else:
            arg_type = str
        self._parser.add_argument(*flags, dest=dest, type=arg_type,
                                  default=None, help=help)
        self._cli_map.append((dest, section, key))

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, args: argparse.Namespace | None = None) -> None:
        """
        Read the config file and merge values onto registered defaults.
        If the project config file exists it is read; otherwise the default
        config file is read.  save() always writes to the project config file.
        After merging the file, any CLI arguments registered via add_cli_arg()
        that are not None are applied as overrides.
        Reports info messages for registered keys not found in the file.
        Must be called after all register_owned(), register_shared(), and
        add_cli_arg() calls, and after parse_args().
        """
        cfg_to_read = None
        if self._project_cfg.exists():
            cfg_to_read = self._project_cfg
        else:
            ctx.info(f"project config {self._project_cfg.as_posix()!r} not found",
                     source=OMIT)
        if not cfg_to_read and self._template_cfg:
            if self._template_cfg.exists():
                cfg_to_read = self._template_cfg
                ctx.info(f"using template {self._template_cfg.as_posix()!r}",
                    source=OMIT)
            else:
                ctx.warning(f"config template {self._template_cfg.as_posix()!r} not found",
                    source=OMIT)
        if not cfg_to_read:
            ctx.info(f"using built-in defaults", source=OMIT)
        # read config file
        if cfg_to_read is not None:
            ctx.push(source=str(cfg_to_read))
            try:
                with open(cfg_to_read, 'r', encoding='utf-8') as f:
                    self._filedata = json.load(f)
            except json.JSONDecodeError as e:
                ctx.error(f"JSON parse error: {e.msg}", lineno=e.lineno, column=e.colno)
            except OSError as e:
                ctx.error(f"could not read config file: {e}", lineno=OMIT, column=OMIT)
            if ctx.no_errors():
                # merge file data onto defaults for all registered sections
                self._merge(self._owned)
                self._merge(self._shared)
            ctx.summarize()
            ctx.pop()
        # apply CLI overrides last so they take precedence over file values
        if args is not None:
            for dest, section, key in self._cli_map:
                val = getattr(args, dest, None)
                if val is not None:
                    self.data[section][key] = val

    def _merge(self, registry: dict[str, dict]) -> None:
        """
        For each section in registry, merge file values onto defaults.
        Only keys present in the defaults are copied; unknown file keys
        are left in _filedata for pass-through on save but do not appear
        in self.data.  Reports info for each registered key not found
        in the file.
        """
        for section, defaults in registry.items():
            file_section = self._filedata.get(section, {})
            for key, default_val in defaults.items():
                if key not in file_section:
                    ctx.info(
                        f"section '{section}': key '{key}' not found in file; "
                        f"using default {default_val!r}",
                        lineno=OMIT, column=OMIT,
                    )
                    # default is already in self.data[section]; nothing to copy
                    continue
                file_val = file_section[key]
                # type must match default to guard against malformed config;
                # bool must be checked before int since bool is a subclass of int
                if isinstance(default_val, bool):
                    if not isinstance(file_val, bool):
                        ctx.warning(
                            f"section '{section}': key '{key}' has wrong type in file "
                            f"(expected bool, got {type(file_val).__name__}); "
                            f"using default {default_val!r}",
                            lineno=OMIT, column=OMIT,
                        )
                        continue
                elif type(file_val) is not type(default_val):
                    ctx.warning(
                        f"section '{section}': key '{key}' has wrong type in file "
                        f"(expected {type(default_val).__name__}, "
                        f"got {type(file_val).__name__}); using default {default_val!r}",
                        lineno=OMIT, column=OMIT,
                    )
                    continue
                self.data[section][key] = file_val

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self) -> None:
        """
        Write current config data back to the config file.

        Owned sections: only registered keys are written; any keys that
        were in the file but are not registered are dropped (housekeeping).

        Shared sections: all keys from the original file are preserved;
        registered keys are updated with current values.  Unregistered
        keys from the file pass through unchanged.
        """
        # owned sections: replace entirely with registered keys only
        for section in self._owned:
            self._filedata[section] = dict(self.data[section])
        # shared sections: update file data with current values, preserving
        # any keys we don't know about
        for section in self._shared:
            if section not in self._filedata:
                self._filedata[section] = {}
            self._filedata[section].update(self.data[section])
        # write
        try:
            with open(self._project_cfg, 'w', encoding='utf-8') as f:
                json.dump(self._filedata, f, indent=4)
        except OSError as e:
            print(f"error writing config file '{self._project_cfg}': {e}", file=sys.stderr)
