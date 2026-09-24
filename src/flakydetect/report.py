# =============================================================================
# flakydetect/report.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Formats and outputs the FlakeReport in multiple ways:
#     1. Rich terminal output (color-coded, human-readable)
#     2. JSON file export (machine-readable, for CI/CD pipelines and dashboards)
#
# CONCEPT: Output Formatting / "Presentation Layer"
#   In a well-structured program, generating the data and presenting the data
#   are separate concerns. This file is the "presentation layer" — it takes
#   a FlakeReport (which contains the data) and decides how to display it.
#
#   Why keep it separate?
#   - You can add a new output format (HTML, CSV, Slack webhook) without
#     touching the aggregator or runner.
#   - You can test the data logic independently from the display logic.
#   - If the `rich` library is not installed, you can swap in a plain-text
#     renderer without touching any other file.
#
# CONCEPT: The `rich` library
#   `rich` is a third-party Python library for beautiful terminal output.
#   It provides colored text, tables, progress bars, panels, and more.
#   We use it here instead of manually writing ANSI escape codes like `\033[31m`.
#
#   Install it with: pip install rich
#
# CONCEPT: JSON (JavaScript Object Notation)
#   JSON is a text-based data format that's both human-readable and machine-
#   readable. It's the lingua franca of data exchange on the web. Python's
#   built-in `json` module converts between Python objects and JSON strings.
#
#   Python dict  →  JSON object   { "key": "value" }
#   Python list  →  JSON array    [ 1, 2, 3 ]
#   Python str   →  JSON string   "hello"
#   Python int   →  JSON number   42
#   Python bool  →  JSON boolean  true / false
#   Python None  →  JSON null
#
# =============================================================================

import json  # Standard library: JSON serialization/deserialization
import logging
from pathlib import Path

# `rich` is a third-party library for beautiful terminal output.
# We use a try/except to gracefully handle the case where it's not installed.
# CONCEPT: Graceful degradation
#   Good programs don't crash hard when an optional feature is missing.
#   If `rich` isn't installed, we fall back to plain print() statements.
try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text  # noqa: F401  # kept for potential future use

    HAS_RICH = True  # Flag: rich is available
except ImportError:
    HAS_RICH = False  # Flag: rich is not installed; use plain text

from .models import FlakeReport, FlakeStats

logger = logging.getLogger(__name__)

# =============================================================================
# Color/style constants
# =============================================================================
# Define our color scheme in one place so it's easy to change.
# In `rich`, styles are strings describing color and formatting.
# These are defined as module-level constants (all-caps by convention).
STYLE_FLAKY = "bold yellow"  # Yellow = warning, something needs attention
STYLE_BROKEN = "bold red"  # Red = error, test always fails
STYLE_STABLE = "bold green"  # Green = good, test is healthy
STYLE_HEADING = "bold white"  # White = neutral, for labels
STYLE_DIM = "dim"  # Dim/grey = secondary information


def print_report(report: FlakeReport, verbose: bool = False) -> None:
    """
    Print a human-readable summary of the FlakeReport to the terminal.

    The output includes:
      - A header with run summary (total runs, command, timestamp)
      - A table of flaky tests (if any), sorted by flake rate
      - A table of always-failing tests (if any)
      - A brief stable test summary
      - A final verdict (pass/fail for CI purposes)

    Args:
        report:  The FlakeReport to display.
        verbose: If True, include additional details (failure messages, etc.)
    """
    if HAS_RICH:
        _print_rich(report, verbose=verbose)
    else:
        _print_plain(report, verbose=verbose)


def save_json(report: FlakeReport, output_path: str) -> None:
    """
    Serialize the FlakeReport to a JSON file.

    The JSON output is suitable for:
      - CI/CD pipelines that need machine-readable exit data
      - Dashboards and historical tracking tools
      - Feeding into other scripts for further analysis

    Args:
        report:      The FlakeReport to serialize.
        output_path: The file path to write the JSON to (e.g., "report.json").
    """
    # Build a plain Python dictionary from the report.
    # We can't directly JSON-serialize a dataclass, so we manually construct
    # a dict of serializable types (str, int, float, list, dict, bool, None).
    data = _report_to_dict(report)

    # `Path(output_path)` creates a Path object — Python's modern way to
    # handle file paths. It works on Windows, macOS, and Linux automatically.
    path = Path(output_path)

    # `path.parent.mkdir(parents=True, exist_ok=True)` creates all the
    # directories in the path if they don't exist yet.
    # `parents=True` means create intermediate directories too.
    # `exist_ok=True` means don't raise an error if the directory already exists.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write the JSON to the file.
    # `path.open("w")` opens the file for writing (creates or overwrites).
    # The `with` statement ensures the file is properly closed after writing.
    with path.open("w", encoding="utf-8") as f:
        # `json.dump(data, f, indent=2)` writes the dict as JSON to the file.
        # `indent=2` makes the output "pretty-printed" (indented) instead of
        # one long line — much easier for humans to read.
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info("JSON report saved to %s", output_path)
    print(f"\n💾  Report saved → {output_path}")


# =============================================================================
# Private helper: rich terminal output
# =============================================================================


def _print_rich(report: FlakeReport, verbose: bool) -> None:
    """Render a beautiful rich-formatted report to the terminal."""
    # `Console()` is the main rich object for printing to the terminal.
    console = Console()

    # -----------------------------------------------------------------------
    # Header panel
    # -----------------------------------------------------------------------
    console.print()  # Empty line for spacing
    console.print(
        Panel.fit(
            f"[bold cyan]🔬 Flaky Test Detector[/bold cyan]  "
            f"[dim]v{report.tool_version}[/dim]",
            border_style="cyan",
        )
    )

    # Summary line
    console.print(f"\n[{STYLE_HEADING}]Command:[/]  [white]{report.command}[/]")
    console.print(f"[{STYLE_HEADING}]Runs:[/]      [white]{report.total_runs}[/]")
    console.print(
        f"[{STYLE_HEADING}]Generated:[/] [white]{report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}[/]\n"
    )

    # -----------------------------------------------------------------------
    # Flaky tests table
    # -----------------------------------------------------------------------
    flaky = report.flaky_tests  # List of FlakeStats, sorted by flake rate

    if flaky:
        table = Table(
            title="⚠️  Flaky Tests",
            box=box.ROUNDED,
            border_style="yellow",
            title_style="bold yellow",
            show_lines=True,
        )
        # Add table columns
        table.add_column("Test Name", style="white", no_wrap=False)
        table.add_column("Flake Rate", style="bold yellow", justify="right")
        table.add_column("Pass / Fail", style="white", justify="center")
        table.add_column("Runs", style="dim", justify="right")

        for stat in flaky:
            # Format the pass/fail ratio as "8 / 2"
            pf_ratio = f"[green]{stat.pass_count}[/] / [red]{stat.fail_count}[/]"
            table.add_row(
                stat.name,
                f"{stat.flake_percentage}%",
                pf_ratio,
                str(stat.total_runs),
            )
            # In verbose mode, show the failure messages indented under the row.
            if verbose and stat.messages:
                for msg in stat.messages[:3]:  # Show at most 3 messages
                    table.add_row(f"  [dim italic]↳ {msg[:120]}[/]", "", "", "")

        console.print(table)
        console.print()

    else:
        console.print(f"[{STYLE_STABLE}]✅  No flaky tests detected.[/]\n")

    # -----------------------------------------------------------------------
    # Always-failing tests table
    # -----------------------------------------------------------------------
    broken = report.always_failing_tests

    if broken:
        table = Table(
            title="❌  Always-Failing Tests  (broken, not flaky)",
            box=box.ROUNDED,
            border_style="red",
            title_style="bold red",
        )
        table.add_column("Test Name", style="white")
        table.add_column("Failed", style="bold red", justify="right")
        table.add_column("Runs", style="dim", justify="right")

        for stat in broken:
            table.add_row(stat.name, str(stat.fail_count), str(stat.total_runs))
            if verbose and stat.messages:
                for msg in stat.messages[:2]:
                    table.add_row(f"  [dim italic]↳ {msg[:120]}[/]", "", "")

        console.print(table)
        console.print()

    # -----------------------------------------------------------------------
    # Stable tests summary
    # -----------------------------------------------------------------------
    stable_count = len(report.stable_tests)
    total_count = report.total_tests

    console.print(
        f"[{STYLE_STABLE}]✅  Stable: {stable_count}/{total_count} tests passed consistently.[/]"
    )
    console.print()

    # -----------------------------------------------------------------------
    # Final verdict
    # -----------------------------------------------------------------------
    if report.flaky_tests or report.always_failing_tests:
        console.print(
            Panel(
                f"[bold red]VERDICT: ISSUES FOUND[/bold red]\n"
                f"[red]{len(report.flaky_tests)} flaky test(s)  |  "
                f"{len(report.always_failing_tests)} always-failing test(s)[/red]",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[bold green]VERDICT: ALL TESTS STABLE ✅[/bold green]",
                border_style="green",
            )
        )

    console.print()


# =============================================================================
# Private helper: plain text output (no rich library)
# =============================================================================


def _print_plain(report: FlakeReport, verbose: bool) -> None:
    """Render a plain-text version of the report (no rich library needed)."""
    print()
    print("=" * 60)
    print("   Flaky Test Detector")
    print("=" * 60)
    print(f"Command:   {report.command}")
    print(f"Runs:      {report.total_runs}")
    print(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if report.flaky_tests:
        print("FLAKY TESTS:")
        print("-" * 40)
        for stat in report.flaky_tests:
            print(
                f"  [FLAKY] {stat.name}\n"
                f"          {stat.flake_percentage}%  "
                f"({stat.pass_count} pass / {stat.fail_count} fail of {stat.total_runs} runs)"
            )
            if verbose and stat.messages:
                for msg in stat.messages[:2]:
                    print(f"            → {msg[:100]}")
        print()
    else:
        print("✅  No flaky tests detected.\n")

    if report.always_failing_tests:
        print("ALWAYS-FAILING TESTS (broken):")
        print("-" * 40)
        for stat in report.always_failing_tests:
            print(
                f"  [BROKEN] {stat.name}  (failed {stat.fail_count}/{stat.total_runs} runs)"
            )
        print()

    stable_count = len(report.stable_tests)
    print(
        f"✅  Stable: {stable_count}/{report.total_tests} tests consistently passing."
    )
    print()

    if report.flaky_tests or report.always_failing_tests:
        print("VERDICT: ISSUES FOUND")
        print(
            f"  {len(report.flaky_tests)} flaky | "
            f"{len(report.always_failing_tests)} broken"
        )
    else:
        print("VERDICT: ALL TESTS STABLE")

    print()


# =============================================================================
# Private helper: convert FlakeReport to a plain dict for JSON serialization
# =============================================================================


def _report_to_dict(report: FlakeReport) -> dict:
    """
    Convert a FlakeReport dataclass to a plain Python dictionary.

    JSON serialization requires plain Python types (dict, list, str, int,
    float, bool, None). Dataclass objects are not directly JSON-serializable,
    so we manually convert them here.

    Args:
        report: The FlakeReport to convert.

    Returns:
        A nested dict suitable for passing to `json.dump()`.
    """

    # Helper to convert a single FlakeStats to a dict.
    def stats_to_dict(s: FlakeStats) -> dict:
        return {
            "name": s.name,
            "total_runs": s.total_runs,
            "pass_count": s.pass_count,
            "fail_count": s.fail_count,
            "skip_count": s.skip_count,
            "flake_rate": s.flake_rate,
            "flake_percentage": s.flake_percentage,
            "is_flaky": s.is_flaky,
            "is_always_failing": s.is_always_failing,
            "is_always_passing": s.is_always_passing,
            "messages": s.messages,
        }

    # Build the top-level report dict.
    return {
        "meta": {
            "command": report.command,
            "total_runs": report.total_runs,
            "generated_at": report.generated_at.isoformat(),
            "tool_version": report.tool_version,
        },
        "summary": {
            "total_tests": report.total_tests,
            "flaky_count": len(report.flaky_tests),
            "always_failing_count": len(report.always_failing_tests),
            "stable_count": len(report.stable_tests),
            "has_issues": bool(report.flaky_tests or report.always_failing_tests),
        },
        # All test stats, keyed by test name for easy lookup.
        "tests": {name: stats_to_dict(stat) for name, stat in report.stats.items()},
        # Flaky tests sorted by flake rate, for quick scanning.
        "flaky_tests": [stats_to_dict(s) for s in report.flaky_tests],
        # Always-failing tests.
        "always_failing_tests": [stats_to_dict(s) for s in report.always_failing_tests],
    }
