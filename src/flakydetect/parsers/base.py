# =============================================================================
# flakydetect/parsers/base.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Defines the "abstract base class" (ABC) that all parsers must follow.
#   Think of this like a CONTRACT — any class that wants to be a parser
#   MUST implement the methods defined here.
#
# CONCEPT: Abstract Base Classes (ABCs) and Interfaces
#   In object-oriented programming, an "interface" or "abstract class" defines
#   WHAT something should be able to do, without saying HOW it does it.
#
#   Real-world analogy: Think of a power outlet. It's an "interface" —
#   it defines the shape of plugs that can fit (the contract), but it doesn't
#   care what you plug in. A lamp, a phone charger, a laptop — all "implement"
#   the outlet interface by having the right plug shape.
#
#   Here, `BaseParser` is the outlet. `JUnitXMLParser` and `PytestTextParser`
#   are devices with the right plug. The runner just calls `parser.parse()`
#   without knowing or caring which specific parser it has.
#
# CONCEPT: Why use ABCs instead of just hoping all parsers have a .parse() method?
#   Python's `abc.ABC` and `@abstractmethod` ENFORCE the contract at the
#   Python level. If you create a subclass of BaseParser and forget to
#   implement `.parse()`, Python will raise a `TypeError` when you try to
#   instantiate it — before you've even run any tests.
#
#   This catches bugs at "definition time" rather than "runtime," which is
#   much cheaper to fix.
#
# =============================================================================

# `abc` is Python's standard library module for Abstract Base Classes.
# `ABC` is the base class to inherit from.
# `abstractmethod` is a decorator that marks a method as "must be implemented."
import abc
import logging
from typing import List, Optional

# Import the data model we return from our parsers.
from ..models import TestResult

# CONCEPT: relative imports
#   `from ..models import TestResult` means:
#   "Go UP one package level (..) then import TestResult from models."
#   We're in `flakydetect/parsers/base.py`, so `..` goes up to `flakydetect/`.
#   Then we import from `flakydetect/models.py`.

logger = logging.getLogger(__name__)


class BaseParser(abc.ABC):
    """
    Abstract base class defining the contract for all test output parsers.

    Every parser is responsible for one thing:
        Take raw test output (XML file, stdout text, etc.)
        → Return a list of TestResult objects.

    To add support for a new test framework, you:
        1. Create a new file in parsers/ (e.g., `mocha_json.py`)
        2. Create a class that inherits from BaseParser
        3. Implement the `parse()` method
        4. Add it to `get_parser()` in __init__.py

    That's it. You don't need to change the runner, aggregator, or reporter.
    This is the "Open/Closed Principle" in action:
        - Open for extension (add new parsers)
        - Closed for modification (don't touch existing code)

    Args:
        xml_path: Path to a JUnit XML file (may be None for text parsers).
        stdout:   Captured stdout text from the test run.
        stderr:   Captured stderr text from the test run.
    """

    def __init__(
        self,
        xml_path: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
    ) -> None:
        # Store the inputs as instance attributes so subclasses can access them.
        self.xml_path = xml_path
        self.stdout = stdout or ""   # Default to empty string if None
        self.stderr = stderr or ""   # Default to empty string if None

    # -------------------------------------------------------------------------
    # @abstractmethod
    # -------------------------------------------------------------------------
    # This decorator marks `parse` as ABSTRACT — it has no implementation here.
    # Any class that inherits from BaseParser MUST provide its own implementation.
    # If it doesn't, Python raises a TypeError when you try to create an instance.
    # -------------------------------------------------------------------------
    @abc.abstractmethod
    def parse(self) -> List[TestResult]:
        """
        Parse the test output and return a list of TestResult objects.

        This method MUST be implemented by every concrete (non-abstract) parser.
        The caller (runner.py) will always call `parser.parse()` to get results,
        regardless of which specific parser type it is.

        Returns:
            A list of TestResult objects, one per test that ran.
            Returns an empty list if no results could be parsed.
        """
        # `...` (Ellipsis) or `pass` is used as a placeholder in abstract methods.
        # This body is never called — subclasses override it with real code.
        ...

    # -------------------------------------------------------------------------
    # Shared helper methods
    # -------------------------------------------------------------------------
    # These are methods that are useful to ALL parsers, so we define them once
    # here and let subclasses inherit them for free.
    # CONCEPT: Inheritance and Code Reuse
    #   When class B inherits from class A, B gets ALL of A's methods.
    #   The child class can call `self._safe_float(...)` even though it's
    #   defined in the parent class. This is one of the core benefits of
    #   inheritance: share code without copy-pasting it.
    # -------------------------------------------------------------------------

    def _safe_float(self, value: Optional[str], default: float = 0.0) -> float:
        """
        Safely convert a string to a float, returning a default if it fails.

        XML attributes and text output often contain numbers as strings.
        If the string is missing or malformed, we don't want to crash —
        we just return the default value.

        Args:
            value:   The string to convert (may be None).
            default: The value to return if conversion fails.

        Returns:
            The float value, or `default` if conversion was not possible.

        Example:
            self._safe_float("0.142")   → 0.142
            self._safe_float(None)      → 0.0
            self._safe_float("N/A")     → 0.0
        """
        if value is None:
            return default
        try:
            # `float(value)` converts a string like "0.142" to the number 0.142.
            return float(value)
        except (ValueError, TypeError):
            # ValueError: string couldn't be converted (e.g., "N/A")
            # TypeError:  value was the wrong type entirely
            logger.debug("Could not convert %r to float; using default %s", value, default)
            return default

    def _normalize_test_name(self, name: str) -> str:
        """
        Normalize a test name to a consistent format.

        Different frameworks format test names differently. For example:
          - pytest:   "tests/test_auth.py::TestLogin::test_timeout"
          - JUnit:    "com.example.TestLogin.testTimeout"
          - GoogleTest: "TestLogin.testTimeout"

        We normalize by stripping leading/trailing whitespace.
        (Future improvement: you could add framework-specific normalization here.)

        Args:
            name: The raw test name string.

        Returns:
            A cleaned-up test name string.
        """
        # `.strip()` removes leading and trailing whitespace characters.
        return name.strip()
