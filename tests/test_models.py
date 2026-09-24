# =============================================================================
# tests/test_models.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Unit tests for the data models in flakydetect/models.py.
#
# CONCEPT: Unit Testing
#   A "unit test" tests a single, isolated piece of code (a "unit") —
#   usually a function or a method. The goal is to verify that, given
#   specific inputs, the unit produces the expected output.
#
#   Writing tests is one of the most important professional programming skills.
#   Tests:
#     - Prove your code works correctly
#     - Catch bugs when you change code later (regression testing)
#     - Document how the code is SUPPOSED to behave (living documentation)
#     - Give you confidence to refactor without breaking things
#
# CONCEPT: pytest
#   pytest is the most popular Python testing framework. Any function whose
#   name starts with `test_` is automatically discovered and run as a test.
#   Inside a test function, you use `assert` to check that something is True.
#
#   If the `assert` passes, the test passes.
#   If the `assert` fails, pytest reports it as a test failure with details.
#
# CONCEPT: assert
#   `assert condition` means "I assert (claim) this condition is True."
#   If it's not True, Python raises an AssertionError and the test fails.
#
#   `assert result == expected, "message"` — the message helps explain the failure.
#
# HOW TO RUN THESE TESTS:
#   From the project root directory, run:
#       pytest tests/ -v
#
# =============================================================================

import pytest
from datetime import datetime

# Import the things we're testing.
# Because we use `src/` layout, make sure you've installed the package
# with `pip install -e .` or run pytest from the project root.
from flakydetect.models import (
    TestResult,
    RunResult,
    FlakeStats,
    FlakeReport,
)


# =============================================================================
# TestResult tests
# =============================================================================

class TestTestResult:
    """
    Tests for the TestResult dataclass.

    CONCEPT: Test Classes
      Grouping related tests into a class (starting with 'Test') is a
      convention that keeps tests organized. pytest discovers and runs
      methods whose names start with 'test_'.
    """

    def test_passed_test_creation(self):
        """A basic passing test result can be created with required fields."""
        result = TestResult(name="test_login", passed=True)

        # Verify the fields we set are stored correctly.
        assert result.name == "test_login"
        assert result.passed is True
        assert result.skipped is False    # Default value
        assert result.duration is None    # Default value
        assert result.message is None     # Default value

    def test_failed_test_creation(self):
        """A failing test result stores all relevant information."""
        result = TestResult(
            name="test_logout",
            passed=False,
            message="AssertionError: Expected 200, got 404",
            duration=0.5,
        )

        assert result.passed is False
        assert result.message == "AssertionError: Expected 200, got 404"
        assert result.duration == 0.5

    def test_skipped_test_creation(self):
        """A skipped test is neither passing nor a failure."""
        result = TestResult(name="test_skipped", passed=False, skipped=True)

        assert result.passed is False
        assert result.skipped is True

    def test_frozen_immutability(self):
        """
        TestResult is frozen — you cannot change its values after creation.

        CONCEPT: Immutability
          An immutable object cannot be changed after it's created.
          This prevents bugs where code accidentally modifies a result
          it was only supposed to READ.
        """
        result = TestResult(name="test_x", passed=True)

        # `pytest.raises(FrozenInstanceError)` asserts that the code inside
        # the `with` block RAISES that specific exception.
        # If it doesn't raise, the test FAILS (because we expected it to raise).
        with pytest.raises(Exception):  # FrozenInstanceError is a subclass of Exception
            result.name = "different_name"  # type: ignore[misc]

    def test_equality_of_identical_results(self):
        """Two TestResult objects with the same values should be equal."""
        r1 = TestResult(name="test_x", passed=True, duration=0.1)
        r2 = TestResult(name="test_x", passed=True, duration=0.1)

        # dataclass(frozen=True) auto-generates __eq__ based on field values.
        assert r1 == r2

    def test_inequality_of_different_results(self):
        """Two TestResult objects with different values should NOT be equal."""
        r1 = TestResult(name="test_x", passed=True)
        r2 = TestResult(name="test_x", passed=False)

        assert r1 != r2


# =============================================================================
# RunResult tests
# =============================================================================

class TestRunResult:
    """Tests for the RunResult dataclass and its computed properties."""

    def _make_run_result(self, passed=3, failed=1, skipped=1) -> RunResult:
        """
        Helper method to create a RunResult with a given mix of outcomes.

        CONCEPT: Test Helpers / Fixtures
          When you find yourself setting up the same data in many tests,
          extract it into a helper. This reduces duplication and makes
          tests easier to read.

          (`passed=3` means "create 3 passing tests by default")
        """
        tests = []

        # Create `passed` number of passing TestResult objects.
        # CONCEPT: range() — generates numbers from 0 to passed-1
        for i in range(passed):
            tests.append(TestResult(name=f"test_pass_{i}", passed=True))

        for i in range(failed):
            tests.append(TestResult(name=f"test_fail_{i}", passed=False))

        for i in range(skipped):
            tests.append(TestResult(name=f"test_skip_{i}", passed=False, skipped=True))

        return RunResult(
            run_index=1,
            tests=tests,
            exit_code=1 if failed > 0 else 0,
            duration=1.5,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
        )

    def test_total_count(self):
        """total property returns the sum of all tests."""
        run = self._make_run_result(passed=3, failed=1, skipped=1)
        assert run.total == 5  # 3 + 1 + 1 = 5

    def test_passed_count(self):
        """passed_count property returns only passing tests."""
        run = self._make_run_result(passed=3, failed=1, skipped=1)
        assert run.passed_count == 3

    def test_failed_count(self):
        """failed_count property excludes skipped tests."""
        run = self._make_run_result(passed=3, failed=1, skipped=1)
        assert run.failed_count == 1  # Skipped should NOT count as failed

    def test_skipped_count(self):
        """skipped_count property returns only skipped tests."""
        run = self._make_run_result(passed=3, failed=1, skipped=2)
        assert run.skipped_count == 2

    def test_all_passing(self):
        """A run with no failures has exit code 0 and all counts make sense."""
        run = self._make_run_result(passed=5, failed=0, skipped=0)
        assert run.passed_count == 5
        assert run.failed_count == 0
        assert run.exit_code == 0


# =============================================================================
# FlakeStats tests
# =============================================================================

class TestFlakeStats:
    """Tests for the FlakeStats dataclass and its computed properties."""

    def test_is_flaky_when_mixed_outcomes(self):
        """A test that sometimes passes and sometimes fails is flaky."""
        stats = FlakeStats(
            name="test_race_condition",
            total_runs=10,
            pass_count=7,
            fail_count=3,
            skip_count=0,
            flake_rate=0.3,
        )

        # It has both passes and failures → it IS flaky.
        assert stats.is_flaky is True

    def test_not_flaky_when_always_passing(self):
        """A test that always passes is NOT flaky."""
        stats = FlakeStats(
            name="test_stable",
            total_runs=10,
            pass_count=10,
            fail_count=0,
            skip_count=0,
            flake_rate=0.0,
            is_always_passing=True,
        )
        assert stats.is_flaky is False

    def test_not_flaky_when_always_failing(self):
        """A test that always fails is broken (not flaky) — it never passes."""
        stats = FlakeStats(
            name="test_broken",
            total_runs=10,
            pass_count=0,
            fail_count=10,
            skip_count=0,
            flake_rate=0.0,
            is_always_failing=True,
        )
        # is_flaky requires BOTH pass_count > 0 AND fail_count > 0.
        assert stats.is_flaky is False

    def test_flake_percentage_conversion(self):
        """flake_percentage converts the 0–1 rate to 0–100 correctly."""
        stats = FlakeStats(
            name="test_x",
            total_runs=10,
            pass_count=8,
            fail_count=2,
            skip_count=0,
            flake_rate=0.2,
        )
        # 0.2 × 100 = 20.0%
        assert stats.flake_percentage == 20.0

    def test_flake_percentage_rounding(self):
        """flake_percentage rounds to 1 decimal place."""
        stats = FlakeStats(
            name="test_y",
            total_runs=3,
            pass_count=2,
            fail_count=1,
            skip_count=0,
            flake_rate=1/3,  # 0.333...
        )
        # 0.333... × 100 = 33.3...  →  rounded to 33.3
        assert stats.flake_percentage == 33.3


# =============================================================================
# FlakeReport tests
# =============================================================================

class TestFlakeReport:
    """Tests for the FlakeReport dataclass and its derived properties."""

    def _make_report(self) -> FlakeReport:
        """Create a sample FlakeReport with a mix of test outcomes."""
        stats = {
            "test_flaky_1": FlakeStats(
                name="test_flaky_1",
                total_runs=10,
                pass_count=7,
                fail_count=3,
                skip_count=0,
                flake_rate=0.3,
            ),
            "test_flaky_2": FlakeStats(
                name="test_flaky_2",
                total_runs=10,
                pass_count=9,
                fail_count=1,
                skip_count=0,
                flake_rate=0.1,
            ),
            "test_broken": FlakeStats(
                name="test_broken",
                total_runs=10,
                pass_count=0,
                fail_count=10,
                skip_count=0,
                flake_rate=0.0,
                is_always_failing=True,
            ),
            "test_stable": FlakeStats(
                name="test_stable",
                total_runs=10,
                pass_count=10,
                fail_count=0,
                skip_count=0,
                flake_rate=0.0,
                is_always_passing=True,
            ),
        }

        return FlakeReport(
            command="pytest tests/",
            total_runs=10,
            stats=stats,
            run_results=[],
            generated_at=datetime(2024, 1, 1),
            tool_version="0.1.0",
        )

    def test_flaky_tests_sorted_by_flake_rate(self):
        """flaky_tests returns only flaky tests, sorted by flake_rate descending."""
        report = self._make_report()
        flaky = report.flaky_tests

        # Only the two flaky tests should appear.
        assert len(flaky) == 2

        # First should be the highest flake rate.
        assert flaky[0].name == "test_flaky_1"  # 30% flake rate
        assert flaky[1].name == "test_flaky_2"  # 10% flake rate

    def test_always_failing_tests(self):
        """always_failing_tests returns only the broken tests."""
        report = self._make_report()
        broken = report.always_failing_tests

        assert len(broken) == 1
        assert broken[0].name == "test_broken"

    def test_stable_tests(self):
        """stable_tests returns only tests that always pass."""
        report = self._make_report()
        stable = report.stable_tests

        assert len(stable) == 1
        assert stable[0].name == "test_stable"

    def test_total_tests(self):
        """total_tests returns the count of unique tests in stats."""
        report = self._make_report()
        assert report.total_tests == 4  # 2 flaky + 1 broken + 1 stable
