# =============================================================================
# flakydetect/aggregator.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   After running the test suite N times, we have N RunResult objects, each
#   containing many TestResult objects. The aggregator's job is to combine all
#   of these into a single FlakeReport — computing statistics like:
#     - How many times did "test_login" pass vs fail across all runs?
#     - Which tests flipped between pass and fail? (flaky)
#     - Which tests always fail? (broken)
#     - What is the overall flake rate for each test?
#
# CONCEPT: Data Aggregation
#   "Aggregation" means combining many individual data points into summary
#   statistics. This is the same thing spreadsheets do with SUM, AVERAGE, etc.
#   Here, we're doing it programmatically for test results.
#
# CONCEPT: Collections and defaultdict
#   Python's `collections` module has specialized container types beyond
#   the basic list, dict, and set. We use `defaultdict` here, which is a
#   dict that automatically creates a default value for missing keys.
#
#   Regular dict: `d["missing_key"]` raises KeyError
#   defaultdict:  `d["missing_key"]` returns the default (e.g., an empty list)
#
#   This is very useful when building up lists grouped by key, since you
#   don't need to check "does this key exist yet?" before appending.
#
# =============================================================================

import logging
from collections import defaultdict   # Specialized dict with auto-defaults
from datetime import datetime
from typing import List, Dict

from .models import RunResult, FlakeStats, FlakeReport, TestResult
from . import __version__             # Import our tool's version number

logger = logging.getLogger(__name__)


class Aggregator:
    """
    Combines multiple RunResult objects into a single FlakeReport.

    The aggregator is the "statistical brain" of flakydetect. It takes the
    raw pass/fail data from each run and computes:
      - Per-test pass/fail/skip counts across all runs
      - Flake rate (percentage of runs where the test was inconsistent)
      - Classification (flaky vs. always-failing vs. stable)

    Usage:
        aggregator = Aggregator(run_results)
        report = aggregator.aggregate()

    Args:
        run_results: A list of RunResult objects (one per test run).
        command:     The original command that was run (stored in the report).
    """

    def __init__(self, run_results: List[RunResult], command: str) -> None:
        self.run_results = run_results
        self.command = command

        # The total number of VALID runs (runs that produced results).
        # This may be less than num_runs if some runs crashed badly.
        self.total_runs = len(run_results)

    def aggregate(self) -> FlakeReport:
        """
        Process all run results and return a complete FlakeReport.

        Algorithm overview:
          1. Collect every test name seen across all runs.
          2. For each test, gather the list of outcomes (pass/fail/skip) across runs.
          3. Compute statistics (counts, flake rate, classification).
          4. Build and return a FlakeReport with all the stats.

        Returns:
            A FlakeReport object containing all computed statistics.
        """
        if not self.run_results:
            logger.warning("No run results to aggregate — returning empty report.")
            return self._build_empty_report()

        logger.info(
            "Aggregating results from %d run(s)...", self.total_runs
        )

        # -----------------------------------------------------------------------
        # Step 1: Group test outcomes by test name across all runs.
        # -----------------------------------------------------------------------
        # We want a structure like:
        #   {
        #     "test_login":   [TestResult(passed=True), TestResult(passed=False), ...],
        #     "test_logout":  [TestResult(passed=True), TestResult(passed=True), ...],
        #   }
        #
        # `defaultdict(list)` creates a dict where any missing key automatically
        # gets an empty list as its value. This means we can do:
        #   outcomes["test_login"].append(result)
        # ...without needing to first check if "test_login" is in the dict.
        outcomes: Dict[str, List[TestResult]] = defaultdict(list)

        # Iterate over every run result, then every test in that run.
        # CONCEPT: Nested loops
        #   The outer loop goes through runs (1st, 2nd, 3rd, etc.)
        #   The inner loop goes through each individual test result in that run.
        #   Together, they process every single test outcome from every run.
        for run_result in self.run_results:
            for test_result in run_result.tests:
                # Group this test result under its test name.
                outcomes[test_result.name].append(test_result)

        logger.info(
            "Found %d unique test names across %d run(s).",
            len(outcomes),
            self.total_runs,
        )

        # -----------------------------------------------------------------------
        # Step 2: Compute FlakeStats for each unique test name.
        # -----------------------------------------------------------------------
        stats: Dict[str, FlakeStats] = {}

        # `.items()` on a dict returns (key, value) pairs so we can iterate both.
        # CONCEPT: tuple unpacking
        #   `for name, test_list in outcomes.items():`
        #   unpacks each pair into two variables at once.
        for test_name, test_list in outcomes.items():
            flake_stats = self._compute_stats(test_name, test_list)
            stats[test_name] = flake_stats

        # -----------------------------------------------------------------------
        # Step 3: Build and return the final FlakeReport.
        # -----------------------------------------------------------------------
        report = FlakeReport(
            command=self.command,
            total_runs=self.total_runs,
            stats=stats,
            run_results=self.run_results,
            generated_at=datetime.now(),
            tool_version=__version__,
        )

        # Log a brief summary of what we found.
        logger.info(
            "Aggregation complete: %d flaky, %d broken, %d stable test(s).",
            len(report.flaky_tests),
            len(report.always_failing_tests),
            len(report.stable_tests),
        )

        return report

    def _compute_stats(
        self, test_name: str, outcomes: List[TestResult]
    ) -> FlakeStats:
        """
        Compute FlakeStats for a single test given its outcomes across all runs.

        Args:
            test_name: The fully-qualified name of the test.
            outcomes:  A list of TestResult objects, one per run the test appeared in.

        Returns:
            A FlakeStats object with all computed statistics.
        """
        total_runs = len(outcomes)

        # Count how many times each outcome occurred.
        # CONCEPT: sum() with a generator expression
        #   `sum(1 for r in outcomes if r.passed)` is equivalent to:
        #       count = 0
        #       for r in outcomes:
        #           if r.passed:
        #               count += 1
        #   But more concise. The `sum()` adds up all the 1s, giving the count.
        pass_count = sum(1 for r in outcomes if r.passed)
        skip_count = sum(1 for r in outcomes if r.skipped)
        fail_count = sum(1 for r in outcomes if not r.passed and not r.skipped)

        # -----------------------------------------------------------------------
        # Compute the flake rate.
        # -----------------------------------------------------------------------
        # A test is "flaky" if it sometimes passes and sometimes fails.
        # The "flake rate" is the proportion of runs where the test gave an
        # inconsistent result relative to the majority outcome.
        #
        # We define it as: min(pass_count, fail_count) / total_runs
        #
        # Why min()? Because:
        #   - If a test passes 8/10 times and fails 2/10 times, it flaked 2 times.
        #   - If a test passes 2/10 and fails 8/10, it flaked 2 times the same way.
        #   - We take the minority count as "the flips."
        #   - Dividing by total gives the fraction of runs that were the "exception."
        #
        # Special cases:
        #   - If total_runs == 0: avoid division by zero, rate = 0.
        #   - If pass_count == 0: test always fails (broken), rate = 0 (not flaky).
        #   - If fail_count == 0: test always passes (stable), rate = 0.
        if total_runs == 0:
            flake_rate = 0.0
        else:
            flake_rate = min(pass_count, fail_count) / total_runs

        # Classify the test.
        is_always_failing = fail_count == total_runs and skip_count == 0
        is_always_passing = pass_count == total_runs

        # Collect unique failure messages for display in the report.
        # We use a set comprehension to deduplicate:
        #   {expr for item in iterable if condition}
        # Similar to a list comprehension but produces a set (unique values only).
        unique_messages = list(
            {
                r.message
                for r in outcomes
                if r.message is not None and not r.passed
            }
        )

        return FlakeStats(
            name=test_name,
            total_runs=total_runs,
            pass_count=pass_count,
            fail_count=fail_count,
            skip_count=skip_count,
            flake_rate=flake_rate,
            is_always_failing=is_always_failing,
            is_always_passing=is_always_passing,
            messages=unique_messages,
        )

    def _build_empty_report(self) -> FlakeReport:
        """Build a FlakeReport with no data (used when there are no run results)."""
        return FlakeReport(
            command=self.command,
            total_runs=0,
            stats={},
            run_results=[],
            generated_at=datetime.now(),
            tool_version=__version__,
        )
