# =============================================================================
# flakydetect/parsers/junit_xml.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Parses JUnit XML output — the standard format used by pytest, JUnit (Java),
#   GoogleTest (C++), and many other test frameworks. Because we parse a
#   standardized XML format instead of scraping raw text, this parser works
#   across multiple languages "for free."
#
# CONCEPT: The JUnit XML Format
#   JUnit XML looks something like this (simplified):
#
#   <testsuites>
#     <testsuite name="tests/test_auth.py" tests="3" failures="1" time="0.5">
#       <testcase name="test_login" classname="tests.test_auth" time="0.1"/>
#       <testcase name="test_logout" classname="tests.test_auth" time="0.2">
#         <failure message="AssertionError">Expected True, got False</failure>
#       </testcase>
#       <testcase name="test_register" classname="tests.test_auth" time="0.2">
#         <skipped/>
#       </testcase>
#     </testsuite>
#   </testsuites>
#
#   Key observations:
#   - A <testcase> with NO child elements = PASSED
#   - A <testcase> with a <failure> child = FAILED
#   - A <testcase> with an <error> child = ERROR (treated as failure)
#   - A <testcase> with a <skipped> child = SKIPPED
#
# CONCEPT: XML (eXtensible Markup Language)
#   XML is a structured data format using angle-bracket "tags." It's older
#   than JSON but still widely used, especially in Java/enterprise tooling.
#   Python's `xml.etree.ElementTree` module (from the standard library)
#   lets us parse XML into a tree structure we can navigate.
#
# =============================================================================

import logging
import xml.etree.ElementTree as ET  # Standard library XML parser
from typing import List, Optional

from ..models import TestResult
from .base import BaseParser

logger = logging.getLogger(__name__)


class JUnitXMLParser(BaseParser):
    """
    Parses JUnit-format XML files to extract individual test results.

    JUnit XML is the most widely supported test output format across ecosystems:
      - Python: pytest with `--junitxml` flag
      - Java: JUnit 4/5, TestNG
      - C++: GoogleTest with `--gtest_output=xml:...`
      - JavaScript: jest with jest-junit reporter
      - Go: gotestsum

    By parsing this single format, we get multi-language support almost for free.

    The parser walks the XML tree, looking for <testcase> elements, and
    inspects each one for child elements (<failure>, <error>, <skipped>)
    to determine the outcome.
    """

    def parse(self) -> List[TestResult]:
        """
        Parse the JUnit XML file and return a list of TestResult objects.

        Returns:
            List of TestResult objects parsed from the XML.
            Returns an empty list if the file doesn't exist, is empty, or is malformed.
        """
        # Guard clause: check if we even have an XML path to work with.
        # CONCEPT: Guard Clauses (early returns)
        #   A "guard clause" checks for error conditions at the TOP of a function
        #   and returns early. This avoids deep nesting (if inside if inside if...)
        #   and makes the "happy path" (normal case) easier to read.
        if not self.xml_path:
            logger.warning("JUnitXMLParser called with no xml_path. Returning empty.")
            return []

        # Try to read and parse the XML file.
        try:
            # `ET.parse()` reads the XML file from disk and returns an
            # ElementTree object — a tree structure representing the XML.
            tree = ET.parse(self.xml_path)

            # `.getroot()` returns the top-level element of the XML tree.
            # For JUnit XML, this is typically <testsuites> or <testsuite>.
            root = tree.getroot()

        except FileNotFoundError:
            logger.warning(
                "JUnit XML file not found at %s. " "Did pytest write it successfully?",
                self.xml_path,
            )
            return []

        except ET.ParseError as e:
            # The file exists but is not valid XML (could be truncated, malformed, etc.)
            logger.warning("Failed to parse XML from %s: %s", self.xml_path, e)
            return []

        # Collect all <testcase> elements from anywhere in the XML tree.
        # CONCEPT: findall() with XPath
        #   `.//testcase` means "find ALL <testcase> elements anywhere in the tree"
        #   (the `//` means "at any depth"). This handles both:
        #     <testsuites> → <testsuite> → <testcase>   (nested)
        #     <testsuite>  → <testcase>                  (one level)
        testcase_elements = root.findall(".//testcase")

        if not testcase_elements:
            logger.warning(
                "Parsed XML from %s but found no <testcase> elements.",
                self.xml_path,
            )
            return []

        # Parse each <testcase> element into a TestResult object.
        # Build our list by applying `_parse_testcase()` to every element.
        results: List[TestResult] = []

        for elem in testcase_elements:
            # Try to parse this testcase. If something goes wrong with a single
            # test, log it and move on rather than failing the whole parse.
            try:
                result = self._parse_testcase(elem)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.debug("Error parsing testcase element: %s", e, exc_info=True)
                continue

        logger.debug("Parsed %d test results from %s", len(results), self.xml_path)
        return results

    def _parse_testcase(self, elem: ET.Element) -> Optional[TestResult]:
        """
        Parse a single <testcase> XML element into a TestResult.

        Args:
            elem: An XML Element representing one <testcase> node.

        Returns:
            A TestResult object, or None if the element is malformed.
        """
        # Extract the `name` and `classname` attributes from the XML element.
        # CONCEPT: .get() on a dict (or XML element)
        #   `.get("name", "")` means "get the value of attribute 'name';
        #   if it doesn't exist, return '' (empty string) as the default."
        #   This is safer than `elem.attrib["name"]`, which would raise a
        #   KeyError if "name" is missing.
        classname = elem.get("classname", "")
        name = elem.get("name", "")

        # Build a fully-qualified test name by combining classname and name.
        # Most frameworks produce output like "tests.test_auth::test_login"
        # which we reconstruct from the two separate attributes.
        if classname and name:
            # Join class name and test name with "::" (pytest convention).
            full_name = f"{classname}::{name}"
        elif name:
            full_name = name
        else:
            # Can't identify the test — skip it.
            logger.debug("Skipping <testcase> element with no name attribute.")
            return None

        # Normalize the name using the base class helper.
        full_name = self._normalize_test_name(full_name)

        # Extract the duration from the "time" attribute.
        # XML stores everything as strings, so we convert it to a float.
        duration = self._safe_float(elem.get("time"), default=0.0)

        # -----------------------------------------------------------------------
        # Determine the test outcome by inspecting child elements.
        # -----------------------------------------------------------------------
        # CONCEPT: XML children
        #   In XML, elements can have "children" — nested elements inside them.
        #   `elem.find("failure")` looks for a direct child named <failure>.
        #   If found, `.find()` returns that child element; otherwise it returns None.
        # -----------------------------------------------------------------------

        # Check for <skipped> child → test was skipped.
        skipped_elem = elem.find("skipped")
        if skipped_elem is not None:
            return TestResult(
                name=full_name,
                passed=False,
                skipped=True,
                duration=duration,
                message=skipped_elem.get("message"),
            )

        # Check for <failure> child → test failed with an assertion error.
        failure_elem = elem.find("failure")
        if failure_elem is not None:
            # Get the failure message from the element's text content or `message` attribute.
            # `elem.text` is the text directly inside the element:
            #   <failure message="AssertionError">Long traceback here</failure>
            #                                      ^^^^^^^^^^^^^^^^^^^^  ← this is .text
            message = failure_elem.get("message") or failure_elem.text
            return TestResult(
                name=full_name,
                passed=False,
                skipped=False,
                duration=duration,
                message=message,
            )

        # Check for <error> child → test raised an unexpected exception (not an assertion).
        error_elem = elem.find("error")
        if error_elem is not None:
            message = error_elem.get("message") or error_elem.text
            return TestResult(
                name=full_name,
                passed=False,
                skipped=False,
                duration=duration,
                message=message,
            )

        # No <failure>, <error>, or <skipped> child → test passed.
        return TestResult(
            name=full_name,
            passed=True,
            skipped=False,
            duration=duration,
            message=None,
        )
