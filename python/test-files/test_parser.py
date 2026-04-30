# test_parser.py
# Test script for bloc_parser.py lexer and parser.
# Run from any directory; locates bloc_parser.py relative to this file.
#
# Each test case runs bloc_parser.py as a subprocess so that sys.exit()
# in the parser does not terminate the test script.

import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
PARSER     = os.path.join(PYTHON_DIR, "bloc_parser.py")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

pass_count = 0
fail_count = 0

def run_test(name: str, bloc_file: str,
             expect_success: bool, expect_fragment: str = "") -> None:
    """
    Run bloc_parser.py on bloc_file as a subprocess.

    name            -- human-readable test name
    bloc_file       -- path to the .bloc file (or a nonexistent path)
    expect_success  -- True if the parser should succeed (exit 0)
    expect_fragment -- if non-empty, this string must appear in the output
                       (stdout + stderr combined) for the test to pass
    """
    global pass_count, fail_count

    result = subprocess.run(
        [sys.executable, PARSER, bloc_file],
        capture_output = True,
        text           = True,
    )

    succeeded  = (result.returncode == 0)
    output     = result.stdout + result.stderr
    frag_found = (expect_fragment == "") or (expect_fragment in output)

    if succeeded == expect_success and frag_found:
        print(f"  PASS: {name}")
        pass_count += 1
    else:
        print(f"  FAIL: {name}")
        if succeeded != expect_success:
            print(f"    expected {'success' if expect_success else 'failure'}, "
                  f"got {'success' if succeeded else 'failure'}")
        if not frag_found:
            print(f"    expected fragment: {expect_fragment!r}")
        print(f"    output: {output.strip()!r}")
        fail_count += 1
    if result.stderr.strip():
        print(f"    stderr: {result.stderr.strip()}")

def test_file(name: str, filename: str,
              expect_success: bool, expect_fragment: str = "") -> None:
    """Convenience wrapper: resolve filename relative to THIS_DIR."""
    run_test(name, os.path.join(THIS_DIR, filename), expect_success, expect_fragment)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

print("\n--- Encoding and file access ---")

test_file("UTF-8 (should succeed)",
          "UTF-8.bloc",
          expect_success  = True)

test_file("ANSI/ASCII (should succeed)",
          "ANSI.bloc",
          expect_success  = True)

test_file("UTF-8 with BOM (non-ASCII on line 1)",
          "UTF-8-BOM.bloc",
          expect_success  = False,
          expect_fragment = "Non-ASCII")

test_file("UTF-16 LE (UnicodeDecodeError)",
          "UTF-16LE.bloc",
          expect_success  = False,
          expect_fragment = "Unicode decode")

test_file("UTF-16 BE (UnicodeDecodeError)",
          "UTF-16BE.bloc",
          expect_success  = False,
          expect_fragment = "Unicode decode")

run_test("File not found",
         os.path.join(THIS_DIR, "does_not_exist.bloc"),
         expect_success  = False,
         expect_fragment = "not found")

test_file("Non-ASCII character in UTF-8 file",
          "test_nonascii.bloc",
          expect_success  = False,
          expect_fragment = "Non-ASCII")

print("\n--- Lexer happy paths ---")

test_file("All lexer happy paths",
          "test_lexer_ok.bloc",
          expect_success  = True)

print("\n--- Lexer error paths ---")

test_file("Misplaced description (/// without statement)",
          "test_misplaced_desc.bloc",
          expect_success  = False,
          expect_fragment = "Misplaced description")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{pass_count + fail_count} tests: {pass_count} passed, {fail_count} failed")
