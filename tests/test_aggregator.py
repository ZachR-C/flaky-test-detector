# =============================================================================
# tests/test_aggregator.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Unit tests for the Aggregator class (flakydetect/aggregator.py).
#
# CONCEPT: Testing Business Logic
#   The aggregator is where the most important "business logic" lives —
#   the rules that define what makes a test "flaky" vs "broken" vs "stable."
#   These rules need to be tested very carefully because they determine
#   what we report to the user. A bug here could cause false positives
#   (reporting a healthy test as flaky) or false negatives (missing real flakes).
#
# CONCEPT: Parametrize
#   `@pytest.mark.parametrize` lets you run the same test function with
#   many different input/output pairs. Instead of writing:
#
#       def test_flake_rate_3_of_10(): ...
#       def test_flake_rate_5_of_10(): ...
#       def test_flake_rate_0_of_10(): ...
#
#   You write one test and provide a table of cases. pytest runs it once
#   per row, reporting each as a separate test case.
#
# =============================================================================

from datetime import datetime
from typing import List

import pytest

from flakydetect.aggregator import Aggregator
from flakydetect.models import RunResult, TestResult

# =============================================================================
# Shared helpers
# =============================================================================


def make_test_result(name: str, passed: bool, skipped: bool = False) -> TestResult:
    """Create a simple TestResult for testing."""
    return TestResult(name=name, passed=passed, skipped=skipped)


def make_run_result(run_index: int, tests: List[TestResult]) -> RunResult:
    """Create a RunResult wrapping a list of TestResults."""
    failed = any(not t.passed for t in tests)
    return RunResult(
        run_index=run_index,
        tests=tests,
        exit_code=1 if failed else 0,
        duration=1.0,
        timestamp=datetime(2024, 1, 1),
    )


class TestAggregator:
    """Tests for the Aggregator class."""

    def test_empty_run_results_returns_empty_report(self):
        """Aggregating with no run results produces an empty report."""
        aggregator = Aggregator(run_results=[], command="pytest tests/")
        report = aggregator.aggregate()

        assert report.total_runs == 0
        assert report.total_tests == 0
        assert report.flaky_tests == []
        assert report.always_failing_tests == []

    def test_all_passing_tests_are_stable(self):
        """If a test passes in every run, it should be marked as stable."""
        runs = [
            make_run_result(i, [make_test_result("test_a", passed=True)])
            for i in range(1, 6)  # 5 runs, all passing
        ]

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        assert len(report.flaky_tests) == 0
        stats = report.stats["test_a"]
        assert stats.is_always_passing is True
        assert stats.is_flaky is False

    def test_always_failing_test_is_not_flaky(self):
        """A test that fails in EVERY run is broken (not flaky)."""
        runs = [
            make_run_result(i, [make_test_result("test_broken", passed=False)])
            for i in range(1, 6)
        ]

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        stats = report.stats["test_broken"]
        assert stats.is_always_failing is True
        assert stats.is_flaky is False
        assert len(report.flaky_tests) == 0
        assert len(report.always_failing_tests) == 1

    def test_flaky_test_detected_on_mixed_outcomes(self):
        """A test that sometimes passes and sometimes fails is correctly flagged."""
        # Build 10 runs: test_login passes in 7, fails in 3.
        runs = []
        for i in range(1, 11):
            # For runs 1–7, the test passes. For runs 8–10, it fails.
            passed = i <= 7
            runs.append(
                make_run_result(i, [make_test_result("test_login", passed=passed)])
            )

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        # Should detect one flaky test.
        assert len(report.flaky_tests) == 1
        stats = report.stats["test_login"]
        assert stats.is_flaky is True
        assert stats.pass_count == 7
        assert stats.fail_count == 3

    def test_flake_rate_calculation(self):
        """
        Flake rate is min(pass_count, fail_count) / total_runs.

        EXAMPLES:
          10 runs: 8 pass, 2 fail → flake_rate = 2/10 = 0.2
          10 runs: 5 pass, 5 fail → flake_rate = 5/10 = 0.5
        """
        # 8 passing, 2 failing runs
        runs = []
        for i in range(1, 11):
            passed = i <= 8
            runs.append(
                make_run_result(i, [make_test_result("test_flaky", passed=passed)])
            )

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        stats = report.stats["test_flaky"]
        # min(8, 2) / 10 = 0.2
        assert stats.flake_rate == pytest.approx(0.2)

    @pytest.mark.parametrize(
        "pass_count, fail_count, expected_rate",
        [
            # (passes, fails, expected flake rate)
            # CONCEPT: parametrize table — each row is one test case.
            # Format: (input_1, input_2, expected_output)
            (10, 0, 0.0),  # All passing → not flaky
            (0, 10, 0.0),  # All failing → not flaky (broken)
            (5, 5, 0.5),  # 50/50 → very flaky
            (8, 2, 0.2),  # 80/20 → mildly flaky
            (1, 9, 0.1),  # 10% pass → flake_rate = min(1,9)/10 = 0.1
        ],
    )
    def test_flake_rate_parametrized(self, pass_count, fail_count, expected_rate):
        """
        Parametrized test verifying flake rate formula for various pass/fail mixes.

        CONCEPT: Parametrize
          This single test function is run 5 times, once for each row in the
          table above. pytest reports each run separately, so you get clear
          feedback on which specific case failed if something breaks.
        """
        # total runs = pass_count + fail_count (used implicitly via the runs list)
        runs = []
        run_idx = 1

        for _ in range(pass_count):
            runs.append(make_run_result(run_idx, [make_test_result("t", passed=True)]))
            run_idx += 1

        for _ in range(fail_count):
            runs.append(make_run_result(run_idx, [make_test_result("t", passed=False)]))
            run_idx += 1

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        stats = report.stats["t"]
        assert stats.flake_rate == pytest.approx(expected_rate, abs=0.01)

    def test_multiple_tests_aggregated_independently(self):
        """Multiple tests in the same run are tracked separately."""
        runs = []
        for i in range(1, 6):
            tests = [
                make_test_result("test_stable", passed=True),
                make_test_result("test_broken", passed=False),
                # test_flaky passes on odd runs, fails on even runs
                make_test_result("test_flaky", passed=(i % 2 == 1)),
            ]
            runs.append(make_run_result(i, tests))

        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        assert report.stats["test_stable"].is_always_passing is True
        assert report.stats["test_broken"].is_always_failing is True
        assert report.stats["test_flaky"].is_flaky is True

    def test_report_stores_original_command(self):
        """The report records the original test command."""
        runs = [make_run_result(1, [make_test_result("t", passed=True)])]
        aggregator = Aggregator(run_results=runs, command="pytest tests/ -v")
        report = aggregator.aggregate()

        assert report.command == "pytest tests/ -v"

    def test_report_stores_tool_version(self):
        """The report includes the tool version string."""
        from flakydetect import __version__

        runs = [make_run_result(1, [make_test_result("t", passed=True)])]
        aggregator = Aggregator(run_results=runs, command="pytest tests/")
        report = aggregator.aggregate()

        assert report.tool_version == __version__
