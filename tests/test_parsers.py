# =============================================================================
# tests/test_parsers.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Unit tests for the parser modules (JUnit XML and pytest text).
#
# CONCEPT: Testing with Fixtures
#   pytest "fixtures" are functions that set up test data (or objects) and
#   make them available to multiple tests. They use the `@pytest.fixture`
#   decorator and are passed as arguments to test functions.
#
#   This avoids repeating setup code in every test — the fixture runs once
#   (or once per test, depending on scope) and the result is injected.
#
# CONCEPT: Testing with Temporary Files
#   When testing code that reads from files, we don't want to depend on
#   real files on disk (that would make tests fragile and environment-dependent).
#   Instead, we create temporary files with known content, test against them,
#   and delete them when done.
#
#   pytest has a built-in `tmp_path` fixture that provides a temporary
#   directory that's automatically cleaned up after each test.
#
# =============================================================================

import textwrap
from pathlib import Path

import pytest

from flakydetect.parsers.junit_xml import JUnitXMLParser
from flakydetect.parsers.pytest_text import PytestTextParser
from flakydetect.parsers import get_parser


# =============================================================================
# Shared XML content
# =============================================================================
# We define XML strings as module-level constants so they can be reused
# across multiple tests without copy-pasting.

# A well-formed JUnit XML with various outcomes.
# `textwrap.dedent()` removes the common leading whitespace from triple-quoted
# strings, so the XML looks indented in the source but doesn't have extra
# spaces when the string is actually used.
SAMPLE_JUNIT_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
        <testsuite name="tests/test_example.py" tests="4" failures="1" errors="0" skipped="1" time="1.5">
            <testcase classname="tests.test_example" name="test_pass_one" time="0.1"/>
            <testcase classname="tests.test_example" name="test_pass_two" time="0.2"/>
            <testcase classname="tests.test_example" name="test_fail_one" time="0.3">
                <failure message="AssertionError: Expected True, got False">
                    Traceback (most recent call last):
                      assert result == expected
                    AssertionError: Expected True, got False
                </failure>
            </testcase>
            <testcase classname="tests.test_example" name="test_skip_one" time="0.0">
                <skipped message="Test skipped for now"/>
            </testcase>
        </testsuite>
    </testsuites>
""")

# An XML with an <error> child (unexpected exception, not an assertion failure).
SAMPLE_JUNIT_XML_WITH_ERROR = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
        <testsuite name="tests/test_errors.py" tests="1" failures="0" errors="1" skipped="0">
            <testcase classname="tests.test_errors" name="test_raises_exception" time="0.05">
                <error message="RuntimeError: database connection refused">
                    RuntimeError: database connection refused
                </error>
            </testcase>
        </testsuite>
    </testsuites>
""")

EMPTY_JUNIT_XML = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
        <testsuite name="empty" tests="0"/>
    </testsuites>
""")

# Sample verbose pytest output (as captured from stdout with -v flag).
SAMPLE_PYTEST_STDOUT = textwrap.dedent("""\
    ============================= test session starts ==============================
    platform linux -- Python 3.11.0, pytest-7.4.0
    rootdir: /project
    collected 4 items

    PASSED tests/test_example.py::test_pass_one
    PASSED tests/test_example.py::test_pass_two
    FAILED tests/test_example.py::test_fail_one - AssertionError: Expected True, got False
    SKIPPED [1] tests/test_example.py::test_skip_one: marker

    =========================== short test summary info ============================
    FAILED tests/test_example.py::test_fail_one - AssertionError
    ========================= 2 passed, 1 failed, 1 skipped in 1.50s =========================
""")


# =============================================================================
# JUnit XML Parser Tests
# =============================================================================

class TestJUnitXMLParser:
    """Tests for the JUnitXMLParser."""

    def _write_xml(self, tmp_path: Path, content: str) -> str:
        """Helper: write XML content to a temp file and return its path."""
        # `tmp_path` is a pytest built-in fixture — a temporary directory
        # that exists only for this test run. pytest deletes it automatically.
        xml_file = tmp_path / "junit.xml"

        # `write_text()` writes a string to a file (creating it if needed).
        xml_file.write_text(content, encoding="utf-8")

        # `str()` converts the Path object to a plain string path.
        return str(xml_file)

    def test_parses_passing_tests(self, tmp_path):
        """Passing <testcase> elements (no children) are parsed as passed=True."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        # Filter to only the passing ones.
        passed = [r for r in results if r.passed]
        assert len(passed) == 2  # test_pass_one and test_pass_two

    def test_parses_failed_tests(self, tmp_path):
        """<testcase> elements with <failure> children are parsed as passed=False."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        failed = [r for r in results if not r.passed and not r.skipped]
        assert len(failed) == 1
        assert "test_fail_one" in failed[0].name
        assert failed[0].message is not None  # Should have failure message

    def test_parses_skipped_tests(self, tmp_path):
        """<testcase> elements with <skipped> children are parsed with skipped=True."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        skipped = [r for r in results if r.skipped]
        assert len(skipped) == 1
        assert "test_skip_one" in skipped[0].name

    def test_parses_error_tests(self, tmp_path):
        """<testcase> elements with <error> children are treated as failures."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML_WITH_ERROR)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        assert len(results) == 1
        assert results[0].passed is False
        assert results[0].skipped is False

    def test_parses_test_duration(self, tmp_path):
        """Duration is correctly parsed from the 'time' attribute."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        # Find test_pass_one (time="0.1")
        result = next(r for r in results if "test_pass_one" in r.name)
        assert result.duration == pytest.approx(0.1)  # approx for float comparison

    def test_returns_empty_for_missing_file(self):
        """Returns an empty list if the XML file doesn't exist."""
        parser = JUnitXMLParser(xml_path="/nonexistent/path/junit.xml")
        results = parser.parse()
        assert results == []

    def test_returns_empty_for_no_path(self):
        """Returns an empty list if xml_path is None."""
        parser = JUnitXMLParser(xml_path=None)
        results = parser.parse()
        assert results == []

    def test_returns_empty_for_malformed_xml(self, tmp_path):
        """Returns empty list instead of crashing on malformed XML."""
        path = self._write_xml(tmp_path, "this is not xml at all <<< >>>")
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()
        assert results == []

    def test_returns_empty_for_no_testcases(self, tmp_path):
        """Returns empty list when the XML has no <testcase> elements."""
        path = self._write_xml(tmp_path, EMPTY_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()
        assert results == []

    def test_test_name_is_normalized(self, tmp_path):
        """Test names should not have leading or trailing whitespace."""
        path = self._write_xml(tmp_path, SAMPLE_JUNIT_XML)
        parser = JUnitXMLParser(xml_path=path)
        results = parser.parse()

        for result in results:
            # `.strip()` removes whitespace; if the name is already clean,
            # this should be a no-op and the assertion should pass.
            assert result.name == result.name.strip(), (
                f"Test name has extra whitespace: {result.name!r}"
            )


# =============================================================================
# Pytest Text Parser Tests
# =============================================================================

class TestPytestTextParser:
    """Tests for the PytestTextParser (fallback parser)."""

    def test_parses_passing_tests(self):
        """PASSED lines in verbose output are parsed as passed=True."""
        parser = PytestTextParser(stdout=SAMPLE_PYTEST_STDOUT)
        results = parser.parse()

        passed = [r for r in results if r.passed]
        assert len(passed) == 2

    def test_parses_failed_tests(self):
        """FAILED lines in verbose output are parsed as passed=False."""
        parser = PytestTextParser(stdout=SAMPLE_PYTEST_STDOUT)
        results = parser.parse()

        failed = [r for r in results if not r.passed and not r.skipped]
        assert len(failed) == 1
        assert "test_fail_one" in failed[0].name

    def test_parses_skipped_tests(self):
        """SKIPPED lines are parsed with skipped=True."""
        parser = PytestTextParser(stdout=SAMPLE_PYTEST_STDOUT)
        results = parser.parse()

        skipped = [r for r in results if r.skipped]
        assert len(skipped) == 1

    def test_returns_empty_for_no_stdout(self):
        """Returns empty list when stdout is None or empty."""
        parser = PytestTextParser(stdout=None)
        results = parser.parse()
        assert results == []

    def test_no_duplicate_tests(self):
        """Each test should appear only once even if it shows up in multiple sections."""
        # pytest prints failed tests both in the main run output AND the summary.
        # Our parser should deduplicate.
        parser = PytestTextParser(stdout=SAMPLE_PYTEST_STDOUT)
        results = parser.parse()

        names = [r.name for r in results]
        # `set(names)` removes duplicates; if len is same, no duplicates exist.
        assert len(names) == len(set(names)), "Duplicate test names found!"


# =============================================================================
# get_parser() factory tests
# =============================================================================

class TestGetParser:
    """Tests for the parser factory function."""

    def test_auto_returns_junit_parser_when_xml_exists(self, tmp_path):
        """Auto mode picks JUnit parser when the XML file exists and has content."""
        xml_file = tmp_path / "junit.xml"
        xml_file.write_text(SAMPLE_JUNIT_XML, encoding="utf-8")

        parser = get_parser(
            parser_name="auto",
            xml_path=str(xml_file),
            stdout=SAMPLE_PYTEST_STDOUT,
        )

        # Should be the JUnit XML parser, not the text parser.
        assert isinstance(parser, JUnitXMLParser)

    def test_auto_returns_text_parser_when_no_xml(self):
        """Auto mode falls back to text parser when there's no XML file."""
        parser = get_parser(
            parser_name="auto",
            xml_path=None,
            stdout=SAMPLE_PYTEST_STDOUT,
        )
        assert isinstance(parser, PytestTextParser)

    def test_explicit_junit_parser(self):
        """Requesting 'junit_xml' always returns JUnitXMLParser."""
        parser = get_parser(parser_name="junit_xml")
        assert isinstance(parser, JUnitXMLParser)

    def test_explicit_text_parser(self):
        """Requesting 'pytest_text' always returns PytestTextParser."""
        parser = get_parser(parser_name="pytest_text")
        assert isinstance(parser, PytestTextParser)

    def test_unknown_parser_raises_value_error(self):
        """Requesting an unknown parser name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown parser"):
            get_parser(parser_name="this_does_not_exist")
