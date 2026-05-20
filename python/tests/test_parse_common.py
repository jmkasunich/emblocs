# tests/test_parse_common.py
# Tests for parse_common.py: read_source_file(), read_source_string(),
# ErrorContext, push/pop context, and report().

import pytest
from pathlib import Path
from parse_common import (
    read_source_file,
    read_source_string,
    ctx, report, Severity, OMIT,
    tokenize_line,
    MAX_ENCODING_ERRORS,
)


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


# ---------------------------------------------------------------------------
# read_source_file() tests
# ---------------------------------------------------------------------------

class TestReadSourceFile:

    def test_valid_ascii_file_returns_lines(self, good_dir):
        lines = read_source_file(str(good_dir / "UTF-8.bloc"))
        ctx.pop()
        assert lines is not None
        assert len(lines) > 0

    def test_valid_ascii_file_pushes_context(self, good_dir):
        path = (good_dir / "UTF-8.bloc").as_posix()
        read_source_file(path)
        assert ctx.source == path
        ctx.pop()

    def test_valid_ascii_file_no_errors(self, good_dir):
        read_source_file(str(good_dir / "UTF-8.bloc"))
        assert ctx.no_errors()
        ctx.pop()

    def test_ansi_file_returns_lines(self, good_dir):
        lines = read_source_file(str(good_dir / "ANSI.bloc"))
        ctx.pop()
        assert lines is not None

    def test_file_not_found_returns_none(self, bad_dir):
        lines = read_source_file(str(bad_dir / "does_not_exist.bloc"))
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_file_not_found_reports_error(self, bad_dir, capsys):
        path = str(bad_dir / "does_not_exist.bloc")
        read_source_file(path)
        actual = capsys.readouterr().err.strip()
        expected = "tests/data/bad/does_not_exist.bloc: error: file not found"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        ctx.pop()

    def test_utf16le_returns_none(self, bad_dir):
        lines = read_source_file(str(bad_dir / "UTF-16LE.bloc"))
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_utf16be_returns_none(self, bad_dir):
        lines = read_source_file(str(bad_dir / "UTF-16BE.bloc"))
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_utf16_reports_encoding_error(self, bad_dir, capsys):
        path = str(bad_dir / "UTF-16LE.bloc")
        read_source_file(path)
        actual = capsys.readouterr().err.strip()
        expected = "tests/data/bad/UTF-16LE.bloc: error: file is not valid UTF-8; re-save as UTF-8 and try again"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        ctx.pop()

    def test_utf8_bom_returns_none(self, bad_dir):
        lines = read_source_file(str(bad_dir / "UTF-8-BOM.bloc"))
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_nonascii_returns_none(self, bad_dir):
        lines = read_source_file(str(bad_dir / "test_nonascii.bloc"))
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_nonascii_reports_error_with_line_number(self, bad_dir, capsys):
        path = str(bad_dir / "test_nonascii.bloc")
        read_source_file(path)
        actual = capsys.readouterr().err.strip()
        expected = "tests/data/bad/test_nonascii.bloc:2: error: non-ASCII character"
        assert actual == expected, (
            f"\nEXPECTED: {expected!r}\n"
            f"ACTUAL:   {actual!r}\n"
        )
        ctx.pop()

# ---------------------------------------------------------------------------
# read_source_string() tests
# ---------------------------------------------------------------------------

class TestReadSourceString:

    def test_simple_string_returns_lines(self):
        lines = read_source_string("line one\nline two\n")
        assert lines == ["line one\n", "line two\n"]
        ctx.pop()

    def test_empty_string_returns_empty_list(self):
        lines = read_source_string("")
        assert lines == []
        ctx.pop()

    def test_default_source_label(self):
        read_source_string("hello\n")
        assert ctx.source == "<string>"
        ctx.pop()

    def test_custom_source_label(self):
        read_source_string("hello\n", source="my_input")
        assert ctx.source == "my_input"
        ctx.pop()

    def test_no_errors_for_clean_string(self):
        read_source_string("block foo\npin float input in\n")
        assert ctx.no_errors()
        ctx.pop()

    def test_nonascii_string_returns_none(self):
        lines = read_source_string("hello\ncaf\u00e9\n")
        assert lines is None
        assert not ctx.no_errors()
        ctx.pop()

    def test_nonascii_reports_correct_line(self, capsys):
        read_source_string("good line\nbad caf\u00e9\n")
        captured = capsys.readouterr()
        assert "2" in captured.err   # line 2 has the non-ASCII char
        ctx.pop()

    def test_string_without_trailing_newline(self):
        lines = read_source_string("no newline")
        assert lines == ["no newline"]
        ctx.pop()

    def test_max_encoding_errors_cutoff(self, capsys):
        # generate more than MAX_ENCODING_ERRORS non-ASCII lines
        bad_text = "caf\u00e9\n" * (MAX_ENCODING_ERRORS + 5)
        lines = read_source_string(bad_text)
        captured = capsys.readouterr()
        assert lines is None
        assert "too many" in captured.err
        # should not report more than MAX_ENCODING_ERRORS individual errors
        assert captured.err.count("non-ASCII") <= MAX_ENCODING_ERRORS
        ctx.pop()


# ---------------------------------------------------------------------------
# ErrorContext and context stack tests
# ---------------------------------------------------------------------------

class TestErrorContext:

    def test_push_creates_clean_context(self):
        ctx.push(source="test.py")
        assert ctx.source == "test.py"
        assert ctx.error_count == 0
        assert ctx.warning_count == 0
        assert ctx.info_count == 0
        ctx.pop()

    def test_nested_contexts(self):
        ctx.push(source="outer.py")
        ctx.push(source="inner.py")
        assert ctx.source == "inner.py"
        ctx.pop()
        assert ctx.source == "outer.py"
        ctx.pop()

    def test_no_errors_true_when_clean(self):
        ctx.push()
        assert ctx.no_errors()
        ctx.pop()

    def test_no_errors_false_after_error(self):
        ctx.push()
        report(Severity.ERROR, "test error")
        assert not ctx.no_errors()
        ctx.pop()

    def test_clean_true_when_clean(self):
        ctx.push()
        assert ctx.clean()
        ctx.pop()

    def test_clean_false_after_warning(self):
        ctx.push()
        report(Severity.WARNING, "test warning")
        assert not ctx.clean()
        ctx.pop()

    def test_error_count_increments(self):
        ctx.push()
        report(Severity.ERROR, "error 1")
        report(Severity.ERROR, "error 2")
        assert ctx.error_count == 2
        ctx.pop()

    def test_warning_count_increments(self):
        ctx.push()
        report(Severity.WARNING, "warning 1")
        assert ctx.warning_count == 1
        ctx.pop()


# ---------------------------------------------------------------------------
# ErrorContext and context stack tests
# ---------------------------------------------------------------------------

class TestTokenizeLine:

    def test_empty_string_returns_empty_list(self):
        assert tokenize_line("", 1) == []

    def test_whitespace_only_returns_empty_list(self):
        assert tokenize_line("   \t  ", 1) == []

    def test_single_token(self):
        tokens = tokenize_line("hello", 1)
        assert len(tokens) == 1
        assert tokens[0].text == "hello"
        assert tokens[0].line == 1
        assert tokens[0].column == 1

    def test_multiple_tokens(self):
        tokens = tokenize_line("foo bar baz", 1)
        assert len(tokens) == 3
        assert tokens[0].text == "foo"
        assert tokens[1].text == "bar"
        assert tokens[2].text == "baz"

    def test_column_numbers_are_correct(self):
        tokens = tokenize_line("foo bar baz", 1)
        assert tokens[0].column == 1
        assert tokens[1].column == 5
        assert tokens[2].column == 9

    def test_leading_whitespace_column(self):
        tokens = tokenize_line("   foo", 1)
        assert tokens[0].column == 4

    def test_tab_separator(self):
        tokens = tokenize_line("foo\tbar", 1)
        assert len(tokens) == 2
        assert tokens[0].text == "foo"
        assert tokens[1].text == "bar"

    def test_line_number_stored(self):
        tokens = tokenize_line("foo bar", 42)
        assert tokens[0].line == 42
        assert tokens[1].line == 42

    def test_special_token_assign(self):
        tokens = tokenize_line("=1.5", 1)
        assert len(tokens) == 1
        assert tokens[0].text == "=1.5"

    def test_special_token_connect(self):
        tokens = tokenize_line("+enc.output", 1)
        assert len(tokens) == 1
        assert tokens[0].text == "+enc.output"

    def test_special_token_disconnect(self):
        tokens = tokenize_line("-enc.output", 1)
        assert len(tokens) == 1
        assert tokens[0].text == "-enc.output"

    def test_special_token_rebind(self):
        tokens = tokenize_line("-+enc.output", 1)
        assert len(tokens) == 1
        assert tokens[0].text == "-+enc.output"

    def test_mixed_special_and_normal_tokens(self):
        tokens = tokenize_line("signal foo +enc.out", 1)
        assert len(tokens) == 3
        assert tokens[0].text == "signal"
        assert tokens[1].text == "foo"
        assert tokens[2].text == "+enc.out"
