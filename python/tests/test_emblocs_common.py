# tests/test_emblocs_common.py
# Tests for the Config class in emblocs_common.py

from __future__ import annotations
import json
import pytest
from pathlib import Path
from parse_common import ctx
from emblocs_common import Config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# location of the real template config, relative to python/ (the test cwd)
TEMPLATE_CFG = Path("../emblocs_cfg.json")

# minimal defaults used by most tests
OWNED_SECTION   = 'port'
OWNED_DEFAULTS  = {'port': '', 'baud': '115.2K'}
SHARED_SECTION  = 'paths'
SHARED_DEFAULTS = {'bloc_search_paths': []}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_context():
    """Ensure context stack is clean before and after every test."""
    ctx.clear()
    ctx.push(source="<test>")
    yield
    ctx.clear()


@pytest.fixture
def tmp_cfg(tmp_dir):
    """Return a path for a temporary config file that does not exist yet."""
    path = tmp_dir / "test_cfg.json"
    if path.exists():
        path.unlink()
    return path


@pytest.fixture
def basic_config(tmp_cfg):
    """
    A Config with one owned and one shared section, project config not yet
    created.  Template is the real emblocs_cfg.json.
    """
    config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
    config.register_owned(OWNED_SECTION, OWNED_DEFAULTS)
    config.register_shared(SHARED_SECTION, SHARED_DEFAULTS)
    return config


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegistration:

    def test_register_owned_creates_section_with_defaults(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned(OWNED_SECTION, OWNED_DEFAULTS)
        assert config.data[OWNED_SECTION] == OWNED_DEFAULTS

    def test_register_shared_creates_section_with_defaults(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_shared(SHARED_SECTION, SHARED_DEFAULTS)
        assert config.data[SHARED_SECTION] == SHARED_DEFAULTS

    def test_section_returns_live_reference(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned(OWNED_SECTION, OWNED_DEFAULTS)
        ref = config.section(OWNED_SECTION)
        ref['port'] = 'COM3'
        assert config.data[OWNED_SECTION]['port'] == 'COM3'

    def test_section_raises_for_unregistered(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        with pytest.raises(KeyError):
            config.section('nonexistent')

    def test_register_owned_raises_if_already_shared(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_shared(SHARED_SECTION, SHARED_DEFAULTS)
        with pytest.raises(ValueError):
            config.register_owned(SHARED_SECTION, OWNED_DEFAULTS)

    def test_register_shared_raises_if_already_owned(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned(OWNED_SECTION, OWNED_DEFAULTS)
        with pytest.raises(ValueError):
            config.register_shared(OWNED_SECTION, SHARED_DEFAULTS)


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------

class TestLoad:

    def test_reads_template_when_no_project_config(self, tmp_cfg, basic_config, capsys):
        basic_config.load()
        actual = capsys.readouterr().err.strip()
        expected = (
            f"info: project config {tmp_cfg.as_posix()!r} not found,"
            f" reading template '../emblocs_cfg.json'\n"
            f"emblocs_cfg.json: 0 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_file_values_override_defaults(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({
            'port': {'port': 'COM3', 'baud': '9600'}
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        assert config.section('port')['port'] == 'COM3'
        assert config.section('port')['baud'] == '9600'

    def test_missing_key_in_file(self, tmp_cfg, capsys):
        # file has port but not baud
        tmp_cfg.write_text(json.dumps({
            'port': {'port': 'COM3'}
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        assert config.section('port')['port'] == 'COM3'
        assert config.section('port')['baud'] == '115.2K'
        actual = capsys.readouterr().err.strip()
        expected = (
            "test_cfg.json: info: section 'port': key 'baud' not found in file;"
            " using default '115.2K'\n"
            "test_cfg.json: 0 error(s), 0 warning(s), 1 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_type_mismatch(self, tmp_cfg, capsys):
        # baud should be a string, not an int
        tmp_cfg.write_text(json.dumps({
            'port': {'port': 'COM3', 'baud': 9600}
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        assert config.section('port')['baud'] == '115.2K'
        actual = capsys.readouterr().err.strip()
        expected = (
            "test_cfg.json: warning: section 'port': key 'baud' has wrong type in file"
            " (expected str, got int); using default '115.2K'\n"
            "test_cfg.json: 0 error(s), 1 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_json_parse_error(self, tmp_cfg, capsys):
        tmp_cfg.write_text("this is not json {{{")
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        assert config.section('port') == OWNED_DEFAULTS
        actual = capsys.readouterr().err.strip()
        expected = (
            "test_cfg.json:1:1: error: JSON parse error: Expecting value\n"
            "test_cfg.json: 1 error(s), 0 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_no_config_files(self, tmp_cfg, capsys):
        missing_template = tmp_cfg.parent / "nonexistent_template.json"
        config = Config(project_cfg=tmp_cfg, default_cfg=missing_template)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        assert config.section('port') == OWNED_DEFAULTS
        actual = capsys.readouterr().err.strip()
        expected = (
            f"warning: project config {tmp_cfg.as_posix()!r} and"
            f" template config {missing_template.resolve().as_posix()!r} not found;"
            f" using built-in defaults\n"
            f"<config>: 0 error(s), 1 warning(s), 0 info(s)")
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )


# ---------------------------------------------------------------------------
# Real template config tests
# ---------------------------------------------------------------------------

class TestRealTemplateConfig:

    def test_template_config_exists(self):
        assert TEMPLATE_CFG.exists(), \
            f"template config not found at {TEMPLATE_CFG.resolve()}"

    def test_template_config_is_valid_json(self):
        data = json.loads(TEMPLATE_CFG.read_text(encoding='utf-8'))
        assert isinstance(data, dict)

    def test_template_has_paths_section(self):
        data = json.loads(TEMPLATE_CFG.read_text(encoding='utf-8'))
        assert 'paths' in data
        assert 'bloc_search_paths' in data['paths']
        assert isinstance(data['paths']['bloc_search_paths'], list)

    def test_load_from_real_template(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_shared('paths', {'bloc_search_paths': []})
        config.load()
        paths = config.section('paths')['bloc_search_paths']
        assert isinstance(paths, list)
        assert len(paths) > 0


# ---------------------------------------------------------------------------
# CLI override tests
# ---------------------------------------------------------------------------

class TestCliOverrides:

    def test_cli_value_overrides_file_value(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3', 'baud': '115.2K'}}))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        parser = config.base_arg_parser()
        config.add_cli_arg('--port', section='port', key='port',
                           help="serial port name")
        args = parser.parse_args(['--port', 'COM7'])
        config.load(args)
        assert config.section('port')['port'] == 'COM7'

    def test_cli_value_overrides_default(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        parser = config.base_arg_parser()
        config.add_cli_arg('--port', section='port', key='port',
                           help="serial port name")
        args = parser.parse_args(['--port', 'COM9'])
        config.load(args)
        assert config.section('port')['port'] == 'COM9'

    def test_absent_cli_arg_does_not_override(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3', 'baud': '115.2K'}}))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        parser = config.base_arg_parser()
        config.add_cli_arg('--port', section='port', key='port',
                           help="serial port name")
        args = parser.parse_args([])
        config.load(args)
        assert config.section('port')['port'] == 'COM3'

    def test_add_cli_arg_raises_for_unregistered_section(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        parser = config.base_arg_parser()
        with pytest.raises(KeyError):
            config.add_cli_arg('--port', section='port', key='port')

    def test_add_cli_arg_raises_for_unknown_key(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        parser = config.base_arg_parser()
        with pytest.raises(KeyError):
            config.add_cli_arg('--foo', section='port', key='nonexistent')

    def test_add_cli_arg_raises_without_parser(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        with pytest.raises(RuntimeError):
            config.add_cli_arg('--port', section='port', key='port')


# ---------------------------------------------------------------------------
# Save tests
# ---------------------------------------------------------------------------

class TestSave:

    def test_owned_section_round_trips(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        config.section('port')['port'] = 'COM5'
        config.save()
        data = json.loads(tmp_cfg.read_text())
        assert data['port']['port'] == 'COM5'

    def test_owned_section_drops_unregistered_keys(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({
            'port': {'port': 'COM3', 'baud': '115.2K', 'obsolete_key': 'old'}
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        config.save()
        data = json.loads(tmp_cfg.read_text())
        assert 'obsolete_key' not in data['port']

    def test_shared_section_preserves_unregistered_keys(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({
            'paths': {
                'bloc_search_paths': ['$EMBLOCS/src/components'],
                'future_tool_key': 'some_value'
            }
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_shared('paths', {'bloc_search_paths': []})
        config.load()
        config.save()
        data = json.loads(tmp_cfg.read_text())
        assert data['paths']['future_tool_key'] == 'some_value'

    def test_unregistered_sections_pass_through(self, tmp_cfg):
        tmp_cfg.write_text(json.dumps({
            'port': {'port': 'COM3', 'baud': '115.2K'},
            'other_tool_section': {'some_key': 'some_value'}
        }))
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        config.save()
        data = json.loads(tmp_cfg.read_text())
        assert 'other_tool_section' in data
        assert data['other_tool_section']['some_key'] == 'some_value'

    def test_save_creates_project_config(self, tmp_cfg):
        config = Config(project_cfg=tmp_cfg, default_cfg=TEMPLATE_CFG)
        config.register_owned('port', OWNED_DEFAULTS)
        config.load()
        config.save()
        assert tmp_cfg.exists()
