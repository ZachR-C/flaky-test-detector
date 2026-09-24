# =============================================================================
# flakydetect/models.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This file defines all the core "data shapes" used throughout the program.
#   Think of these like blueprints or forms — they describe exactly what
#   information a piece of data contains and what types those fields are.
#
# CONCEPT: What is a Data Model?
#   When you write a program, you're constantly moving data around. Instead
#   of using loose variables like `name = "test_login"` and `passed = True`
#   scattered everywhere, you group related data into a single object.
#   This is called a "data model" or "data class."
#
#   Example WITHOUT a data model (messy and error-prone):
#       test_name = "test_login"
#       test_passed = True
#       test_duration = 0.5
#       # Now you have 3 separate variables that all belong to the same thing
#
#   Example WITH a data model (clean and clear):
#       result = TestResult(name="test_login", passed=True, duration=0.5)
#       # Now it's one object. Can't accidentally mix up which name goes
#       # with which passed flag.
#
# CONCEPT: What is a dataclass?
#   Python's `dataclass` decorator is a shortcut for creating classes that
#   mainly hold data. Instead of writing:
#
#       class TestResult:
#           def __init__(self, name, passed):
#               self.name = name
#               self.passed = passed
#
#   You can write:
#       @dataclass
#       class TestResult:
#           name: str
#           passed: bool
#
#   Python auto-generates __init__, __repr__, __eq__, and more for you.
#
# CONCEPT: Type Annotations (the `: str`, `: bool`, `: List[...]` syntax)
#   Python lets you label what TYPE of value each field should hold.
#   These annotations don't enforce anything at runtime — they're hints
#   for YOU, your teammates, and tools like mypy (a type-checker).
#   They make code much easier to read and catch bugs early.
#
# =============================================================================

# `dataclass` and `field` come from Python's standard library.
# `dataclass` is the decorator that generates boilerplate automatically.
# `field` lets us set per-field options like default factories.
from dataclasses import dataclass, field

# `Optional` means a value can be either a specific type OR None (absent).
# `List` means a list of a specific type, e.g. List[str] = list of strings.
# `Dict` means a dictionary mapping one type to another.
# These come from the `typing` module — Python's type annotation tools.
from typing import Optional, List, Dict

# `datetime` represents a specific point in time (date + time combined).
# We use it to record WHEN a test run happened so we can track trends over time.
from datetime import datetime


# -----------------------------------------------------------------------------
# TestResult
# -----------------------------------------------------------------------------
# Represents the outcome of a SINGLE test in a SINGLE run.
# Example: "test_login passed in 0.42 seconds during run #3"
#
# The `@dataclass` decorator above the class definition tells Python to
# automatically create __init__, __repr__, __eq__ based on the fields below.
# `frozen=True` means the object is IMMUTABLE — once created, you cannot
# change its values. This prevents accidental bugs where you modify a result
# after the fact.
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class TestResult:
    """
    Represents the outcome of a single test case in a single run.

    Attributes:
        name:      The fully-qualified name of the test.
                   Example: "tests/test_auth.py::test_login_timeout"
        passed:    True if the test passed, False if it failed.
        skipped:   True if the test was skipped (e.g., marked with @pytest.mark.skip).
                   Skipped tests are neither passes nor failures.
        duration:  How long the test took to run, in seconds.
                   Optional because some parsers don't provide timing info.
        message:   The failure message or error traceback, if the test failed.
                   Optional because passing tests don't have failure messages.
    """

    # The name of the test.
    # `str` means this must be a string (text).
    name: str

    # Whether the test passed.
    # `bool` means this can only be True or False.
    passed: bool

    # Whether the test was skipped.
    # We default this to False because most tests are not skipped.
    # `field(default=False)` sets the default value when not provided.
    skipped: bool = field(default=False)

    # How long the test ran in seconds.
    # `Optional[float]` means it's either a decimal number or None.
    duration: Optional[float] = field(default=None)

    # The failure message (only populated when the test fails).
    # `Optional[str]` means it's either a string or None.
    message: Optional[str] = field(default=None)


# -----------------------------------------------------------------------------
# RunResult
# -----------------------------------------------------------------------------
# Represents the outcome of running the ENTIRE test suite ONE time.
# A single "run" contains many individual TestResults.
# Example: "Run #2 of 10: 38 passed, 3 failed, took 12.4 seconds total"
# -----------------------------------------------------------------------------
@dataclass
class RunResult:
    """
    Represents the outcome of a complete test suite execution (one run).

    A FlakeDetect session runs the test suite N times.
    Each of those N executions produces one RunResult.

    Attributes:
        run_index:   Which run this was (1-based, so first run = 1, not 0).
        tests:       All the individual test outcomes from this run.
        exit_code:   The exit code the test command returned.
                     Exit code 0 = success (all tests passed).
                     Exit code 1 = failure (one or more tests failed).
                     Exit code 2 = usage error (something went wrong with the command).
        duration:    Total wall-clock time for the entire run, in seconds.
        timestamp:   The date and time when this run started.
    """

    # Which run number this is (1 = first run, 2 = second run, etc.)
    run_index: int

    # A list of all individual test outcomes.
    # `List[TestResult]` means: a list where every item is a TestResult object.
    tests: List[TestResult]

    # The integer exit code returned by the test process.
    exit_code: int

    # Total wall-clock time for the entire run, in seconds.
    duration: float

    # When this run started. `datetime` is a type from Python's standard library.
    # We default to None here and set it in the runner so the timestamp
    # reflects the actual start time of the process.
    timestamp: Optional[datetime] = field(default=None)

    # -------------------------------------------------------------------------
    # CONCEPT: Properties
    # A @property is a method that behaves like an attribute.
    # Instead of `result.get_total()`, you call `result.total`.
    # This makes the API more natural and readable.
    # -------------------------------------------------------------------------

    @property
    def total(self) -> int:
        """Returns the total number of tests in this run."""
        # `len()` is a built-in Python function that returns the number of
        # items in a list (or any collection).
        return len(self.tests)

    @property
    def passed_count(self) -> int:
        """Returns the number of tests that passed in this run."""
        # This is called a "list comprehension" — a compact way to filter a list.
        # `[t for t in self.tests if t.passed]` creates a NEW list containing
        # only the TestResult objects where `passed` is True.
        # Then `len(...)` counts how many there are.
        return len([t for t in self.tests if t.passed])

    @property
    def failed_count(self) -> int:
        """Returns the number of tests that failed in this run."""
        # `not t.passed` means "t.passed is False" — i.e., the test failed.
        # We also check `not t.skipped` to exclude skipped tests from the count.
        return len([t for t in self.tests if not t.passed and not t.skipped])

    @property
    def skipped_count(self) -> int:
        """Returns the number of tests that were skipped in this run."""
        return len([t for t in self.tests if t.skipped])


# -----------------------------------------------------------------------------
# FlakeStats
# -----------------------------------------------------------------------------
# Represents the AGGREGATED statistics for a single test across ALL runs.
# After running the suite 10 times, this object holds the answer to:
# "How did test_login do across all 10 runs?"
# -----------------------------------------------------------------------------
@dataclass
class FlakeStats:
    """
    Aggregated flakiness statistics for a single test across multiple runs.

    After running the suite N times, we compute FlakeStats for every test
    that appeared in at least one run.

    Attributes:
        name:         The test's fully-qualified name.
        total_runs:   How many runs included this test.
        pass_count:   How many times it passed.
        fail_count:   How many times it failed.
        skip_count:   How many times it was skipped.
        flake_rate:   The fraction of runs where it flipped (0.0 to 1.0).
                      A test with flake_rate=0.0 is perfectly consistent.
                      A test with flake_rate=1.0 fails every single time
                      (that's not flaky — that's just broken).
        is_always_failing: True if it NEVER passed (broken, not flaky).
        is_always_passing: True if it ALWAYS passed (fully stable).
        messages:     Unique failure messages seen across runs (for debugging).
    """

    name: str
    total_runs: int
    pass_count: int
    fail_count: int
    skip_count: int
    flake_rate: float

    # Set defaults for derived boolean flags
    is_always_failing: bool = field(default=False)
    is_always_passing: bool = field(default=False)

    # A list of unique failure messages seen, for debugging.
    # We use `field(default_factory=list)` instead of `default=[]` because
    # mutable defaults (like lists) are dangerous in dataclasses — they'd be
    # shared across ALL instances. `default_factory=list` creates a NEW list
    # for each instance.
    messages: List[str] = field(default_factory=list)

    @property
    def is_flaky(self) -> bool:
        """
        Returns True if this test is genuinely flaky.

        A test is "flaky" if it SOMETIMES passes and SOMETIMES fails.
        A test that ALWAYS fails is broken (not flaky).
        A test that ALWAYS passes is healthy (not flaky).
        """
        # A test is flaky if it has failed at least once AND passed at least once.
        # `and` means BOTH conditions must be True.
        return self.fail_count > 0 and self.pass_count > 0

    @property
    def flake_percentage(self) -> float:
        """Returns the flake rate as a human-readable percentage (0–100)."""
        # Multiply the 0.0–1.0 fraction by 100 to get a percentage.
        # Round to 1 decimal place for clean display.
        return round(self.flake_rate * 100, 1)


# -----------------------------------------------------------------------------
# FlakeReport
# -----------------------------------------------------------------------------
# The TOP-LEVEL object that holds everything about a complete flaky-test session.
# This is what gets saved to a JSON file or printed to the terminal.
# -----------------------------------------------------------------------------
@dataclass
class FlakeReport:
    """
    The complete report for a FlakeDetect session.

    This is the top-level object produced after all runs are complete.
    It contains both the raw run data and the computed statistics.

    Attributes:
        command:          The shell command that was run (e.g., "pytest tests/").
        total_runs:       How many times the command was executed.
        stats:            A dict mapping test name → FlakeStats for every test.
        run_results:      The raw per-run data (one RunResult per run).
        generated_at:     When this report was generated.
        tool_version:     The version of flakydetect that generated this report.
    """

    command: str
    total_runs: int

    # `Dict[str, FlakeStats]` is a dictionary where:
    #   - Keys are strings (the test name)
    #   - Values are FlakeStats objects
    # Example: { "test_login": FlakeStats(...), "test_logout": FlakeStats(...) }
    stats: Dict[str, FlakeStats]

    # The raw list of RunResult objects — one per execution.
    run_results: List[RunResult]

    # When this report was created (so you can compare reports over time).
    generated_at: datetime

    # Which version of the tool generated this, for forward-compatibility.
    tool_version: str

    # -------------------------------------------------------------------------
    # Derived properties — computed on the fly from the stored data
    # -------------------------------------------------------------------------

    @property
    def flaky_tests(self) -> List[FlakeStats]:
        """Returns only the tests that are genuinely flaky, sorted by flake rate."""
        # `self.stats.values()` returns all the FlakeStats objects in the dict.
        # We filter to only those where `is_flaky` is True.
        # `sorted(...)` returns a new sorted list. The `key` argument tells
        # Python WHAT to sort by. `lambda s: s.flake_rate` is an anonymous
        # function that takes a FlakeStats object `s` and returns its flake_rate.
        # `reverse=True` means highest flake rate first (descending order).
        return sorted(
            [s for s in self.stats.values() if s.is_flaky],
            key=lambda s: s.flake_rate,
            reverse=True,
        )

    @property
    def always_failing_tests(self) -> List[FlakeStats]:
        """Returns tests that failed in every single run (broken, not flaky)."""
        return sorted(
            [s for s in self.stats.values() if s.is_always_failing],
            key=lambda s: s.name,
        )

    @property
    def stable_tests(self) -> List[FlakeStats]:
        """Returns tests that passed in every single run they were present for."""
        return [s for s in self.stats.values() if s.is_always_passing]

    @property
    def total_tests(self) -> int:
        """Returns the total number of unique tests seen across all runs."""
        return len(self.stats)
