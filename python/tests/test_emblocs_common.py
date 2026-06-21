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
def cfg():
    """A fresh Config with no registered keys."""
    return Config()


# ---------------------------------------------------------------------------
# set_by_name / get_by_name / name_exists
# ---------------------------------------------------------------------------

class TestSetAndGet:

    def test_set_and_get_leaf(self, cfg):
        cfg.set_by_name('port.port', '')
        assert cfg.get_by_name('port.port') == ''

    def test_set_creates_intermediate_dicts(self, cfg):
        cfg.set_by_name('scope.channel_00.gain', 1.0)
        assert cfg.get_by_name('scope.channel_00.gain') == 1.0

    def test_get_subtree(self, cfg):
        cfg.set_by_name('port.port', '')
        cfg.set_by_name('port.baud', '115.2K')
        result = cfg.get_by_name('port')
        assert result == {'port': '', 'baud': '115.2K'}

    def test_get_subtree_is_live_reference(self, cfg):
        cfg.set_by_name('port.port', '')
        ref = cfg.get_by_name('port')
        ref['port'] = 'COM3'
        assert cfg.get_by_name('port.port') == 'COM3'

    def test_get_raises_for_missing_name(self, cfg):
        with pytest.raises(KeyError):
            cfg.get_by_name('nonexistent')

    def test_get_raises_for_missing_leaf(self, cfg):
        cfg.set_by_name('port.port', '')
        with pytest.raises(KeyError):
            cfg.get_by_name('port.nonexistent')

    def test_name_exists_true(self, cfg):
        cfg.set_by_name('port.port', '')
        assert cfg.name_exists('port.port') is True

    def test_name_exists_true_for_subtree(self, cfg):
        cfg.set_by_name('port.port', '')
        assert cfg.name_exists('port') is True

    def test_name_exists_false(self, cfg):
        assert cfg.name_exists('nonexistent') is False

    def test_overwrite_same_type(self, cfg):
        cfg.set_by_name('port.baud', '115.2K')
        cfg.set_by_name('port.baud', '9600')
        assert cfg.get_by_name('port.baud') == '9600'

    def test_overwrite_wrong_type_preserves_value_emits_warning(self, cfg, capsys):
        cfg.set_by_name('port.baud', '115.2K')
        cfg.set_by_name('port.baud', 9600)
        actual = capsys.readouterr().err.strip()
        expected = (
            "warning: 'port.baud' has wrong type (expected str, got int);"
            " keeping current value '115.2K'")
        assert cfg.get_by_name('port.baud') == '115.2K'
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_bool_not_confused_with_int_preserves_value_emits_warning(self, cfg, capsys):
        cfg.set_by_name('flags.enabled', True)
        cfg.set_by_name('flags.enabled', 1)
        actual = capsys.readouterr().err.strip()
        expected = (
            "warning: 'flags.enabled' has wrong type (expected bool, got int);"
            " keeping current value True")
        assert cfg.get_by_name('flags.enabled') is True
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_structural_conflict_preserves_existing_emits_error(self, cfg, capsys):
        cfg.set_by_name('scope.horizontal', 1000)
        cfg.set_by_name('scope.horizontal.offset', 50)
        actual = capsys.readouterr().err.strip()
        expected = (
            "error: 'scope.horizontal.offset': 'horizontal' is already set as a"
            " leaf value; cannot use it as an intermediate node")
        assert cfg.get_by_name('scope.horizontal') == 1000
        assert not cfg.name_exists('scope.horizontal.offset')
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )


# ---------------------------------------------------------------------------
# items()
# ---------------------------------------------------------------------------

class TestItems:

    def test_items_flat(self, cfg):
        cfg.set_by_name('port.port', '')
        cfg.set_by_name('port.baud', '115.2K')
        result = dict(cfg.items())
        assert result == {'port.port': '', 'port.baud': '115.2K'}

    def test_items_nested(self, cfg):
        cfg.set_by_name('scope.channel_00.gain', 1.0)
        cfg.set_by_name('scope.channel_00.offset', 0.0)
        result = dict(cfg.items())
        assert result == {
            'scope.channel_00.gain': 1.0,
            'scope.channel_00.offset': 0.0,
        }

    def test_items_with_prefix(self, cfg):
        cfg.set_by_name('scope.channel_00.gain', 1.0)
        cfg.set_by_name('scope.channel_01.gain', 2.0)
        cfg.set_by_name('port.baud', '115.2K')
        result = dict(cfg.items('scope.channel_00'))
        assert result == {'scope.channel_00.gain': 1.0}

    def test_items_prefix_single_leaf(self, cfg):
        cfg.set_by_name('port.baud', '115.2K')
        result = dict(cfg.items('port.baud'))
        assert result == {'port.baud': '115.2K'}

    def test_items_prefix_not_found(self, cfg):
        with pytest.raises(KeyError):
            dict(cfg.items('nonexistent'))

    def test_items_empty_config(self, cfg):
        result = dict(cfg.items())
        assert result == {}


# ---------------------------------------------------------------------------
# load_file()
# ---------------------------------------------------------------------------

class TestLoadFile:

    def test_load_simple_file(self, cfg, tmp_cfg):
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3', 'baud': '9600'}}))
        cfg.set_by_name('port.port', '')
        cfg.set_by_name('port.baud', '115.2K')
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('port.port') == 'COM3'
        assert cfg.get_by_name('port.baud') == '9600'

    def test_load_overrides_defaults(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3'}}))
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('port.port') == 'COM3'

    def test_load_preserves_unmentioned_keys(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        cfg.set_by_name('port.baud', '115.2K')
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3'}}))
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('port.baud') == '115.2K'

    def test_load_adds_unknown_keys(self, cfg, tmp_cfg):
        tmp_cfg.write_text(json.dumps({'new_section': {'new_key': 'value'}}))
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('new_section.new_key') == 'value'

    def test_load_type_mismatch_preserves_existing_emits_warning(self, cfg, tmp_cfg, capsys):
        cfg.set_by_name('port.baud', '115.2K')
        tmp_cfg.write_text(json.dumps({'port': {'baud': 9600}}))
        cfg.load_file(tmp_cfg)
        actual = capsys.readouterr().err.strip()
        expected = (
            "warning: 'port.baud' has wrong type (expected str, got int);"
            " keeping current value '115.2K'\n"
            "test_cfg.json: 0 error(s), 1 warning(s), 0 info(s)")
        assert cfg.get_by_name('port.baud') == '115.2K'
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_second_load_overrides_first(self, cfg, tmp_dir):
        cfg.set_by_name('port.port', '')
        first = tmp_dir / "first.json"
        second = tmp_dir / "second.json"
        first.write_text(json.dumps({'port': {'port': 'COM3'}}))
        second.write_text(json.dumps({'port': {'port': 'COM7'}}))
        cfg.load_file(first)
        cfg.load_file(second)
        assert cfg.get_by_name('port.port') == 'COM7'

    def test_two_loads_non_overlapping_keys_both_survive(self, cfg, tmp_dir):
        first = tmp_dir / "first.json"
        second = tmp_dir / "second.json"
        first.write_text(json.dumps({'port': {'port': 'COM3'}}))
        second.write_text(json.dumps({'port': {'baud': '9600'}}))
        cfg.load_file(first)
        cfg.load_file(second)
        assert cfg.get_by_name('port.port') == 'COM3'
        assert cfg.get_by_name('port.baud') == '9600'

    def test_load_nested_structure(self, cfg, tmp_cfg):
        cfg.set_by_name('scope.channel_00.gain', 1.0)
        tmp_cfg.write_text(json.dumps({
            'scope': {'channel_00': {'gain': 2.5}}
        }))
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('scope.channel_00.gain') == 2.5

    def test_load_returns_true_on_success(self, cfg, tmp_cfg):
        tmp_cfg.write_text(json.dumps({}))
        assert cfg.load_file(tmp_cfg) is True

    def test_load_file_not_found_returns_false_emits_error(self, cfg, tmp_cfg, capsys):
        result = cfg.load_file(tmp_cfg)
        actual = capsys.readouterr().err.strip()
        expected = (
            f"error: config file {tmp_cfg.as_posix()!r} not found\n"
            f"test_cfg.json: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_load_bad_json_returns_false_emits_error(self, cfg, tmp_cfg, capsys):
        tmp_cfg.write_text("this is not json {{{")
        result = cfg.load_file(tmp_cfg)
        actual = capsys.readouterr().err.strip()
        expected = (
            "test_cfg.json:1:1: error: JSON parse error: Expecting value\n"
            "test_cfg.json: 1 error(s), 0 warning(s), 0 info(s)")
        assert result is False
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )

    def test_load_bad_json_leaves_data_unchanged(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', 'COM3')
        tmp_cfg.write_text("this is not json {{{")
        cfg.load_file(tmp_cfg)
        assert cfg.get_by_name('port.port') == 'COM3'


# ---------------------------------------------------------------------------
# Real template config
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

    def test_load_from_real_template(self, cfg):
        cfg.set_by_name('paths.bloc_search_paths', [])
        cfg.load_file(TEMPLATE_CFG)
        paths = cfg.get_by_name('paths.bloc_search_paths')
        assert isinstance(paths, list)
        assert len(paths) > 0


# ---------------------------------------------------------------------------
# CLI: parse_cli / merge_cli / add_cli_arg
# ---------------------------------------------------------------------------

class TestCLI:

    def test_mapped_cli_overrides_default(self, cfg):
        cfg.set_by_name('port.port', '')
        cfg.add_cli_arg('--port', name='port.port', help="serial port")
        cfg.parse_cli(['--port', 'COM3'])
        cfg.merge_cli()
        assert cfg.get_by_name('port.port') == 'COM3'

    def test_mapped_cli_overrides_file_value(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3'}}))
        cfg.load_file(tmp_cfg)
        cfg.add_cli_arg('--port', name='port.port', help="serial port")
        cfg.parse_cli(['--port', 'COM7'])
        cfg.merge_cli()
        assert cfg.get_by_name('port.port') == 'COM7'

    def test_absent_mapped_cli_does_not_override(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        tmp_cfg.write_text(json.dumps({'port': {'port': 'COM3'}}))
        cfg.load_file(tmp_cfg)
        cfg.add_cli_arg('--port', name='port.port', help="serial port")
        cfg.parse_cli([])
        cfg.merge_cli()
        assert cfg.get_by_name('port.port') == 'COM3'

    def test_unmapped_cli_arg_in_namespace(self, cfg):
        cfg.add_cli_arg('--verbose', action='store_true', help="verbose")
        args = cfg.parse_cli(['--verbose'])
        assert args.verbose is True

    def test_unmapped_cli_arg_not_in_data(self, cfg):
        cfg.add_cli_arg('--verbose', action='store_true', help="verbose")
        cfg.parse_cli(['--verbose'])
        cfg.merge_cli()
        assert not cfg.name_exists('verbose')

    def test_cli_type_inferred_from_default_int(self, cfg):
        cfg.set_by_name('text.font_size', 12)
        cfg.add_cli_arg('--font-size', name='text.font_size')
        cfg.parse_cli(['--font-size', '14'])
        cfg.merge_cli()
        assert cfg.get_by_name('text.font_size') == 14
        assert isinstance(cfg.get_by_name('text.font_size'), int)

    def test_cli_type_inferred_from_default_float(self, cfg):
        cfg.set_by_name('scope.time_per_div', 0.1)
        cfg.add_cli_arg('--time-per-div', name='scope.time_per_div')
        cfg.parse_cli(['--time-per-div', '0.5'])
        cfg.merge_cli()
        assert cfg.get_by_name('scope.time_per_div') == pytest.approx(0.5)

    def test_cli_parse_returns_namespace(self, cfg):
        cfg.add_cli_arg('--cfg', help="config file")
        args = cfg.parse_cli(['--cfg', 'myfile.json'])
        assert args.cfg == 'myfile.json'

    def test_merge_cli_without_parse_raises(self, cfg):
        with pytest.raises(RuntimeError):
            cfg.merge_cli()

    def test_add_cli_arg_raises_for_missing_name(self, cfg):
        with pytest.raises(KeyError):
            cfg.add_cli_arg('--port', name='port.port')

    def test_add_cli_arg_raises_for_dict_name(self, cfg):
        cfg.set_by_name('port.port', '')
        with pytest.raises(ValueError):
            cfg.add_cli_arg('--port', name='port')

    def test_short_and_long_flags(self, cfg):
        cfg.set_by_name('port.port', '')
        cfg.add_cli_arg('-p', '--port', name='port.port', help="serial port")
        cfg.parse_cli(['-p', 'COM3'])
        cfg.merge_cli()
        assert cfg.get_by_name('port.port') == 'COM3'

    def test_deep_path_cli_arg(self, cfg):
        cfg.set_by_name('scope.channel_00.gain', 1.0)
        cfg.add_cli_arg('--ch0-gain', name='scope.channel_00.gain')
        cfg.parse_cli(['--ch0-gain', '2.5'])
        cfg.merge_cli()
        assert cfg.get_by_name('scope.channel_00.gain') == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# save_file()
# ---------------------------------------------------------------------------

class TestSaveFile:

    def test_save_and_reload(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', 'COM3')
        cfg.set_by_name('port.baud', '9600')
        cfg.save_file(tmp_cfg)
        cfg2 = Config()
        cfg2.load_file(tmp_cfg)
        assert cfg2.get_by_name('port.port') == 'COM3'
        assert cfg2.get_by_name('port.baud') == '9600'

    def test_save_creates_file(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        assert not tmp_cfg.exists()
        cfg.save_file(tmp_cfg)
        assert tmp_cfg.exists()

    def test_save_writes_valid_json(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', 'COM3')
        cfg.save_file(tmp_cfg)
        data = json.loads(tmp_cfg.read_text())
        assert isinstance(data, dict)

    def test_save_preserves_nested_structure(self, cfg, tmp_cfg):
        cfg.set_by_name('scope.channel_00.gain', 2.5)
        cfg.set_by_name('scope.channel_00.offset', 0.0)
        cfg.save_file(tmp_cfg)
        data = json.loads(tmp_cfg.read_text())
        assert data['scope']['channel_00']['gain'] == 2.5
        assert data['scope']['channel_00']['offset'] == 0.0

    def test_save_preserves_unknown_keys(self, cfg, tmp_cfg):
        # unknown keys loaded from file should survive save
        tmp_cfg.write_text(json.dumps({'unknown': {'key': 'value'}}))
        cfg.load_file(tmp_cfg)
        cfg.save_file(tmp_cfg)
        data = json.loads(tmp_cfg.read_text())
        assert data['unknown']['key'] == 'value'

    def test_full_round_trip_with_cli(self, cfg, tmp_cfg):
        cfg.set_by_name('port.port', '')
        cfg.set_by_name('port.baud', '115.2K')
        cfg.add_cli_arg('--port', name='port.port')
        cfg.parse_cli(['--port', 'COM5'])
        cfg.merge_cli()
        cfg.save_file(tmp_cfg)
        cfg2 = Config()
        cfg2.set_by_name('port.port', '')
        cfg2.set_by_name('port.baud', '115.2K')
        cfg2.load_file(tmp_cfg)
        assert cfg2.get_by_name('port.port') == 'COM5'
        assert cfg2.get_by_name('port.baud') == '115.2K'
