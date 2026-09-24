# =============================================================================
# flakydetect/parsers/pytest_text.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   A fallback parser that extracts test results by parsing pytest's raw
#   terminal output (stdout) using regular expressions.
#
# WHEN IS THIS USED?
#   - When `--junitxml` was not injected (e.g., user is running a custom script)
#   - When the XML file is missing or empty for some reason
#   - When the user explicitly requests `--parser pytest_text`
#
# CONCEPT: Regular Expressions (regex)
#   A regular expression is a pattern that describes a set of strings.
#   For example, the pattern `r"(\w+)\s+passed"` would match:
#     "3 passed"  →  captures "3"
#     "42 passed" →  captures "42"
#
#   Python's `re` module provides regex functionality.
#   Key functions:
#     - `re.search(pattern, text)`: find the FIRST match anywhere in `text`
#     - `re.findall(pattern, text)`: find ALL matches, return as a list
#     - `re.compile(pattern)`: pre-compile a pattern for repeated use (faster)
#
# CONCEPT: Raw strings (`r"..."`)
#   In Python, `\n` means "newline" and `\t` means "tab" inside regular strings.
#   In regex, `\w` means "word character" and `\d` means "digit."
#   A raw string (`r"..."`) tells Python NOT to interpret backslashes specially,
#   so `r"\w"` is literally backslash + w, which is what regex expects.
#   Always use raw strings for regex patterns to avoid confusion.
#
# =============================================================================

import logging
import re
from typing import List, Optional

from ..models import TestResult
from .base import BaseParser

logger = logging.getLogger(__name__)

# =============================================================================
# Pre-compiled regular expressions
# =============================================================================
#
# We compile these patterns ONCE at module load time rather than inside a
# function. This is a performance optimization — compiling a regex is not free,
# and if `parse()` is called many times, we avoid re-compiling the same pattern
# on every call.
#
# ANATOMY OF A REGEX PATTERN:
#   r"^PASSED\s+(.+)$"
#      ^               — match beginning of line (with re.MULTILINE flag)
#       PASSED         — match the literal word "PASSED"
#             \s+      — match one or more whitespace characters
#                (.+)  — CAPTURE GROUP: capture one or more of any character
#                    $  — match end of line
#
# Pytest's verbose output (-v) looks like:
#   PASSED tests/test_auth.py::test_login
#   FAILED tests/test_auth.py::test_timeout - AssertionError: expected True
#   SKIPPED tests/test_something.py::test_skip
# =============================================================================

# Pattern to match a PASSING test line in verbose pytest output.
# `re.MULTILINE` makes `^` and `$` match the start/end of each LINE,
# not the start/end of the entire string.
_PASSED_PATTERN = re.compile(
    r"^PASSED\s+(.+?)(?:\s+-\s+.+)?$",
    re.MULTILINE,
)

# Pattern to match a FAILING test line.
# `(?:\s+-\s+.+)?` is a NON-capturing group (?: ... ) that optionally matches
# " - some failure message" at the end. We don't capture it here; we look
# for the detailed message separately.
_FAILED_PATTERN = re.compile(
    r"^FAILED\s+(.+?)(?:\s+-\s+.+)?$",
    re.MULTILINE,
)

# Pattern to match a SKIPPED test line.
_SKIPPED_PATTERN = re.compile(
    r"^SKIPPED\s+\[.+?\]\s+(.+)$",
    re.MULTILINE,
)

# Pattern to match pytest's summary line at the bottom:
#   "5 passed, 2 failed, 1 skipped in 12.34s"
# This tells us total counts, useful as a sanity check.
_SUMMARY_PATTERN = re.compile(
    r"(\d+)\s+passed.*?(\d+)\s+failed.*?in\s+([\d.]+)s",
    re.DOTALL,
)

# Pattern to match individual failure details in the FAILURES section.
# Pytest prints a separator line like:
#   "________________ test_name ________________"
# followed by the failure traceback.
_FAILURE_HEADER_PATTERN = re.compile(
    r"^_{5,}\s+(.+?)\s+_{5,}$",
    re.MULTILINE,
)


class PytestTextParser(BaseParser):
    """
    Parses raw pytest terminal output (stdout) to extract test results.

    This parser uses regular expressions to scrape the human-readable output
    that pytest writes to the terminal. It's less reliable than JUnit XML
    (output format can vary with plugins, configuration, terminal width, etc.),
    but serves as a useful fallback.

    This parser REQUIRES pytest to be run with the `-v` (verbose) flag
    to produce per-test status lines. Without `-v`, pytest only shows dots
    and letters which are harder to parse reliably.

    Note:
        This parser is intentionally less sophisticated than JUnitXMLParser.
        For production use, prefer the JUnit XML approach.
    """

    def parse(self) -> List[TestResult]:
        """
        Parse pytest's verbose stdout and return TestResult objects.

        Returns:
            A list of TestResult objects. Empty list if no results found.
        """
        # If there's no stdout at all, there's nothing to parse.
        if not self.stdout:
            logger.warning(
                "PytestTextParser called with no stdout. Returning empty results."
            )
            return []

        results: List[TestResult] = []

        # -----------------------------------------------------------------------
        # CONCEPT: Sets for deduplication
        #   A `set` is like a list, but it only stores UNIQUE values.
        #   `{"a", "b", "a"}` → `{"a", "b"}` (duplicate removed automatically)
        #   We use sets to track which test names we've already seen, so
        #   if a test appears in multiple sections of pytest output, we don't
        #   count it twice.
        # -----------------------------------------------------------------------
        seen_names = set()

        # Find all PASSED test lines.
        for match in _PASSED_PATTERN.finditer(self.stdout):
            # `match.group(1)` returns the text captured by the first `()` group.
            # In our pattern, group(1) is the test name.
            name = self._normalize_test_name(match.group(1))
            if name not in seen_names:
                seen_names.add(name)
                results.append(TestResult(name=name, passed=True, skipped=False))

        # Find all FAILED test lines.
        for match in _FAILED_PATTERN.finditer(self.stdout):
            name = self._normalize_test_name(match.group(1))
            if name not in seen_names:
                seen_names.add(name)
                # Try to find the associated failure message.
                message = self._extract_failure_message(name)
                results.append(
                    TestResult(
                        name=name,
                        passed=False,
                        skipped=False,
                        message=message,
                    )
                )

        # Find all SKIPPED test lines.
        for match in _SKIPPED_PATTERN.finditer(self.stdout):
            name = self._normalize_test_name(match.group(1))
            if name not in seen_names:
                seen_names.add(name)
                results.append(TestResult(name=name, passed=False, skipped=True))

        if not results:
            logger.warning(
                "PytestTextParser found no test results. "
                "Make sure pytest is run with the -v flag.\n"
                "First 500 chars of stdout: %s",
                self.stdout[:500],
            )

        logger.debug("Parsed %d test results from stdout", len(results))
        return results

    def _extract_failure_message(self, test_name: str) -> Optional[str]:
        """
        Attempt to extract the failure message for a specific test from stdout.

        Pytest prints a "FAILURES" section that looks like:
            ________________________ test_name ________________________
            ... traceback content ...
            AssertionError: Expected True, got False

        We look for the separator line containing the test name and extract
        a few lines of content after it as the failure message.

        Args:
            test_name: The full test name to look for in the FAILURES section.

        Returns:
            A short failure message string, or None if not found.
        """
        # Try to find the test name in a failure header line.
        # We search for a pattern like "___ test_name ___" in the output.
        for match in _FAILURE_HEADER_PATTERN.finditer(self.stdout):
            header_name = match.group(1).strip()

            # Check if this failure header corresponds to our test.
            # We use `in` rather than exact equality because pytest sometimes
            # abbreviates the full test path in the header.
            if header_name in test_name or test_name.endswith(header_name):
                # Extract a slice of text after the header as the failure message.
                # `match.end()` gives the character position where the match ended.
                # We take the next 500 characters as a rough "message excerpt."
                start = match.end()
                excerpt = self.stdout[start : start + 500].strip()

                # Return just the first non-empty line as a concise message.
                lines = [line for line in excerpt.splitlines() if line.strip()]
                if lines:
                    # Return the last line (usually the most descriptive assertion error).
                    return lines[-1].strip()

        return None
