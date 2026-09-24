# =============================================================================
# flakydetect/parsers/__init__.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This file does two things:
#     1. Makes `parsers/` a Python package (so you can import from it).
#     2. Exposes a `get_parser()` factory function that selects the right parser
#        based on context (do we have XML output? did the user specify a parser?).
#
# CONCEPT: The Factory Pattern
#   A "factory" is a function or class whose job is to CREATE other objects.
#   Instead of the caller needing to know which specific class to instantiate,
#   they just say "give me a parser" and the factory figures out the details.
#
#   Without a factory:
#       if has_xml:
#           parser = JUnitXMLParser(xml_path)
#       else:
#           parser = PytestTextParser(stdout)
#   ... and you'd repeat this logic everywhere.
#
#   With a factory:
#       parser = get_parser(...)  # handles all the if/else internally
#   ... caller doesn't need to know which parser class was picked.
#
#   This is also called the "Open/Closed Principle" — adding a new parser
#   only requires adding a new class and one branch in get_parser(), without
#   changing any calling code.
#
# =============================================================================

import logging
import os
from typing import Optional

# Import all parsers so `get_parser` can choose between them.
from .base import BaseParser
from .junit_xml import JUnitXMLParser
from .pytest_text import PytestTextParser

logger = logging.getLogger(__name__)


def get_parser(
    parser_name: str = "auto",
    xml_path: Optional[str] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
) -> BaseParser:
    """
    Factory function: select and return the appropriate parser.

    The "auto" mode (default) tries to use JUnit XML if the file exists and
    has content, and falls back to parsing stdout if not.

    Args:
        parser_name: Which parser to use. Options: "auto", "junit_xml", "pytest_text".
        xml_path:    Path to a JUnit XML file (may or may not exist yet).
        stdout:      Raw captured stdout from the test command.
        stderr:      Raw captured stderr from the test command.

    Returns:
        A parser object with a `.parse()` method.

    Raises:
        ValueError: If `parser_name` is not a recognized option.
    """
    # -------------------------------------------------------------------------
    # CONCEPT: if / elif / else  (branching / conditional logic)
    #   `if condition:` runs the indented block if condition is True.
    #   `elif condition:` ("else if") checks another condition if the first was False.
    #   `else:` runs if NONE of the conditions above were True.
    #
    #   Only ONE branch ever runs — Python checks top-to-bottom and stops
    #   at the first matching condition.
    # -------------------------------------------------------------------------

    if parser_name == "junit_xml":
        # User explicitly requested JUnit XML parsing.
        logger.debug("Using explicitly requested JUnit XML parser.")
        return JUnitXMLParser(xml_path=xml_path, stdout=stdout, stderr=stderr)

    elif parser_name == "pytest_text":
        # User explicitly requested text/stdout parsing.
        logger.debug("Using explicitly requested pytest text parser.")
        return PytestTextParser(stdout=stdout, stderr=stderr)

    elif parser_name == "auto":
        # Auto-detect: use JUnit XML if we have a populated file, else stdout.
        xml_available = (
            xml_path is not None
            and os.path.isfile(xml_path)  # File exists on disk
            and os.path.getsize(xml_path) > 0  # File is not empty
        )

        if xml_available:
            logger.debug("Auto-detected JUnit XML output at %s", xml_path)
            return JUnitXMLParser(xml_path=xml_path, stdout=stdout, stderr=stderr)
        else:
            logger.debug(
                "No JUnit XML found (or file empty); falling back to text parser."
            )
            return PytestTextParser(stdout=stdout, stderr=stderr)

    else:
        # The caller passed an unrecognized parser name — raise a clear error.
        # CONCEPT: raise / ValueError
        #   `raise` throws an exception, stopping execution at that point.
        #   `ValueError` is a built-in exception type for "the value given is invalid."
        raise ValueError(
            f"Unknown parser: {parser_name!r}. "
            f"Valid options are: 'auto', 'junit_xml', 'pytest_text'."
        )


# Make these symbols importable directly from `flakydetect.parsers`.
# Example: `from flakydetect.parsers import BaseParser`
__all__ = ["BaseParser", "JUnitXMLParser", "PytestTextParser", "get_parser"]
