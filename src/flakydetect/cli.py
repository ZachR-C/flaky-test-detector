# =============================================================================
# flakydetect/cli.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This is the "entry point" — the code that runs when a user types
#   `flaky-detect` in their terminal. It:
#     1. Parses the command-line arguments the user provided
#     2. Validates them and gives helpful error messages if something's wrong
#     3. Sets up logging based on verbosity flags
#     4. Orchestrates the runner → aggregator → reporter pipeline
#     5. Exits with the appropriate exit code for CI/CD
#
# CONCEPT: CLI (Command-Line Interface)
#   A CLI is a text-based interface where users interact with a program by
#   typing commands. Unlike a GUI (Graphical User Interface) with buttons and
#   windows, a CLI is driven entirely by text.
#
#   Example:
#     flaky-detect --cmd "pytest tests/" --runs 10 --output report.json
#
#   Arguments that start with `--` are "options" or "flags."
#   They let the user customize behavior without changing the code.
#
# CONCEPT: typer
#   `typer` is a Python library that makes building CLIs incredibly easy.
#   It uses Python's type annotations (`: str`, `: int`) to:
#     - Automatically parse command-line arguments into the right types
#     - Generate help text (`--help`) automatically
#     - Provide tab-completion in modern shells
#     - Validate inputs (e.g., "runs must be >= 1")
#
# CONCEPT: Exit Codes
#   When a program finishes, it returns a number called an "exit code" to
#   the operating system. By convention:
#     0 = success (everything is fine)
#     1 = general error (something went wrong)
#     2 = flaky tests found (specific to our tool)
#
#   CI/CD systems (like GitHub Actions) read this exit code to decide
#   whether a build passes or fails. If we exit with 0, the CI step passes.
#   If we exit with anything else, the step fails.
#
# =============================================================================

# Standard library
import logging
from pathlib import Path
from typing import Optional

# Third-party
import typer  # Modern CLI builder (install: pip install typer)
from typing_extensions import Annotated  # For adding descriptions to CLI args

from . import __version__
from .aggregator import Aggregator
from .report import print_report, save_json

# Local package imports
from .runner import TestRunner

# =============================================================================
# typer App
# =============================================================================
# `typer.Typer()` creates the CLI application object.
# `rich_markup_mode="rich"` allows rich formatting in help text.
# `no_args_is_help=True` shows help when called with no arguments (nice UX).
app = typer.Typer(
    name="flaky-detect",
    help=(
        "🔬 [bold cyan]Flaky Test Detector[/bold cyan] — "
        "Run your test suite N times and detect flaky tests.\n\n"
        "A 'flaky' test is one that [yellow]sometimes passes and sometimes fails[/yellow] "
        "without any code changes. These erode trust in your test suite "
        "and waste engineering time with spurious CI failures."
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
)


# =============================================================================
# Version callback
# =============================================================================
# This function is registered as the callback for `--version`.
# When the user types `flaky-detect --version`, this runs and exits.
def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"flaky-detect version {__version__}")
        # `raise typer.Exit()` tells typer to exit cleanly (exit code 0).
        raise typer.Exit()


# =============================================================================
# Main command
# =============================================================================
# The `@app.command()` decorator registers this function as the main command.
# Typer inspects the function signature and creates CLI arguments from it.
# =============================================================================
@app.command()
def main(
    # -------------------------------------------------------------------------
    # --cmd / -c
    # -------------------------------------------------------------------------
    # `Annotated[str, typer.Option(...)]` tells typer:
    #   - This argument has type `str`
    #   - It's an optional flag (not a positional argument)
    #   - The `...` means it's REQUIRED (no default value)
    #   - `prompt=True` asks the user to type it if they forgot to pass it
    # -------------------------------------------------------------------------
    cmd: Annotated[
        str,
        typer.Option(
            "--cmd",
            "-c",
            help="The test command to run. Example: [dim]pytest tests/[/dim]",
            prompt="Test command to run",
            prompt_required=False,
        ),
    ],
    # -------------------------------------------------------------------------
    # --runs / -n
    # Number of times to run the test suite.
    # We default to 10, which is usually enough to reliably catch flaky tests.
    # -------------------------------------------------------------------------
    runs: Annotated[
        int,
        typer.Option(
            "--runs",
            "-n",
            help="Number of times to run the test suite. More runs = higher confidence.",
            min=1,  # typer validates this automatically — must be >= 1
            max=1000,  # Cap at 1000 to prevent accidents
        ),
    ] = 10,
    # -------------------------------------------------------------------------
    # --output / -o
    # Path to save the JSON report. Optional.
    # -------------------------------------------------------------------------
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Save the report as JSON to this path. Example: [dim]report.json[/dim]",
        ),
    ] = None,
    # -------------------------------------------------------------------------
    # --threshold / -t
    # The minimum flake rate (%) to report. Default 5%.
    # Tests that flake less than this might be noise (e.g., 1 failure in 100 runs).
    # -------------------------------------------------------------------------
    threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            "-t",
            help=(
                "Minimum flake rate %% to flag a test. Tests below this "
                "threshold won't be reported as flaky. Default: 5.0"
            ),
            min=0.0,
            max=100.0,
        ),
    ] = 5.0,
    # -------------------------------------------------------------------------
    # --working-dir / -d
    # Directory to run the command from. Defaults to current directory.
    # -------------------------------------------------------------------------
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--dir",
            "-d",
            help="Working directory for the test command. Defaults to current directory.",
        ),
    ] = None,
    # -------------------------------------------------------------------------
    # --parser
    # Which parser to use for interpreting test output.
    # -------------------------------------------------------------------------
    parser: Annotated[
        str,
        typer.Option(
            "--parser",
            help="Output parser: [dim]auto[/dim] | [dim]junit_xml[/dim] | [dim]pytest_text[/dim]",
        ),
    ] = "auto",
    # -------------------------------------------------------------------------
    # --timeout
    # Kill a single run if it takes longer than this many seconds.
    # -------------------------------------------------------------------------
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Seconds before killing a single run. Default: 300 (5 minutes).",
            min=1,
        ),
    ] = 300,
    # -------------------------------------------------------------------------
    # --verbose / -v
    # Show extra detail (failure messages, per-run status, debug info).
    # -------------------------------------------------------------------------
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v", help="Show detailed output including failure messages."
        ),
    ] = False,
    # -------------------------------------------------------------------------
    # --quiet / -q
    # Suppress all output except the final verdict (useful for CI scripts).
    # -------------------------------------------------------------------------
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet", "-q", help="Suppress all output except the final verdict."
        ),
    ] = False,
    # -------------------------------------------------------------------------
    # --version
    # Print the version number and exit.
    # -------------------------------------------------------------------------
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,  # Process this flag before any other logic
            help="Print version and exit.",
        ),
    ] = None,
) -> None:
    """
    Detect flaky tests by running your test suite multiple times.

    \b
    EXAMPLES:
        flaky-detect --cmd "pytest tests/" --runs 10
        flaky-detect --cmd "pytest tests/ -v" --runs 20 --output report.json
        flaky-detect --cmd "python -m pytest" --runs 5 --threshold 10.0
        flaky-detect --cmd "make test" --runs 15 --dir /path/to/project
    """
    # -------------------------------------------------------------------------
    # Set up logging
    # -------------------------------------------------------------------------
    # CONCEPT: Logging levels
    #   DEBUG:   Very detailed — every step, useful for development
    #   INFO:    Normal progress messages (default)
    #   WARNING: Something unexpected happened but we can continue
    #   ERROR:   Something failed but we may be able to recover
    #   CRITICAL:Something so bad the program must stop
    #
    #   Setting the level to INFO means DEBUG messages are hidden.
    #   Setting it to DEBUG shows everything.
    # -------------------------------------------------------------------------
    log_level = logging.WARNING  # Default: only show warnings and errors

    if verbose:
        log_level = logging.DEBUG
    elif not quiet:
        log_level = logging.INFO

    # Configure the root logger.
    # `format` controls what each log line looks like.
    # `%(levelname)s` → "INFO", "WARNING", etc.
    # `%(name)s` → the module name (e.g., "flakydetect.runner")
    # `%(message)s` → the actual log message
    logging.basicConfig(
        level=log_level,
        format="%(levelname)-8s  %(name)s  %(message)s",
    )

    # -------------------------------------------------------------------------
    # Validate inputs
    # -------------------------------------------------------------------------
    # Even though typer handles basic type validation, we add semantic validation
    # (checks on the MEANING of the values, not just their types).
    if not cmd or not cmd.strip():
        typer.echo("❌  Error: --cmd cannot be empty.", err=True)
        raise typer.Exit(code=1)

    if working_dir and not working_dir.is_dir():
        typer.echo(
            f"❌  Error: --dir {working_dir} is not a valid directory.", err=True
        )
        raise typer.Exit(code=1)

    # Convert threshold from percentage (0–100) to fraction (0.0–1.0)
    # for comparison with flake_rate (which is stored as a fraction).
    threshold_fraction = threshold / 100.0

    # -------------------------------------------------------------------------
    # Print startup info
    # -------------------------------------------------------------------------
    if not quiet:
        typer.echo(f"\n🔬  flaky-detect v{__version__}")
        typer.echo(f"    Command:   {cmd}")
        typer.echo(f"    Runs:      {runs}")
        typer.echo(f"    Threshold: {threshold}%")
        if working_dir:
            typer.echo(f"    Directory: {working_dir}")
        typer.echo()

    # -------------------------------------------------------------------------
    # Run the pipeline: runner → aggregator → reporter
    # -------------------------------------------------------------------------
    # CONCEPT: Pipeline Architecture
    #   We chain three steps where each step's output is the next step's input:
    #
    #   [TestRunner] → List[RunResult]
    #                       ↓
    #               [Aggregator] → FlakeReport
    #                                   ↓
    #                           [print_report / save_json]
    #
    #   Each step is a clean, independent unit that could be replaced
    #   or tested on its own. This is the Unix philosophy: "Do one thing well,
    #   and pipe the output to the next tool."
    # -------------------------------------------------------------------------

    # Step 1: Run the test suite N times.
    runner = TestRunner(
        command=cmd,
        num_runs=runs,
        working_dir=str(working_dir) if working_dir else None,
        timeout=timeout,
        parser_name=parser,
    )

    try:
        run_results = runner.run()
    except Exception as e:
        typer.echo(f"\n❌  Fatal error during test execution:\n   {e}", err=True)
        raise typer.Exit(code=1)

    if not run_results:
        typer.echo(
            "❌  No runs completed successfully. Check your command and try again.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Step 2: Aggregate all run results into a FlakeReport.
    aggregator = Aggregator(run_results=run_results, command=cmd)
    report = aggregator.aggregate()

    # -------------------------------------------------------------------------
    # Apply the threshold: hide tests that are below the flake threshold.
    # -------------------------------------------------------------------------
    # This is done by filtering the stats dict IN PLACE.
    # We keep a test in the report if:
    #   a) it's above the threshold, OR
    #   b) it always fails (broken), OR
    #   c) it's stable (we always show stable tests for completeness)
    if threshold_fraction > 0:
        report.stats = {
            name: stat
            for name, stat in report.stats.items()
            if stat.flake_rate >= threshold_fraction
            or stat.is_always_failing
            or stat.is_always_passing
        }

    # Step 3a: Print the report to the terminal.
    if not quiet:
        print_report(report, verbose=verbose)

    # Step 3b: Save JSON report if requested.
    if output:
        save_json(report, str(output))

    # -------------------------------------------------------------------------
    # Exit with the appropriate exit code.
    # -------------------------------------------------------------------------
    # Exit code 0 → no issues (CI step passes)
    # Exit code 2 → flaky or broken tests found (CI step fails)
    has_issues = bool(report.flaky_tests or report.always_failing_tests)

    if has_issues:
        # `raise typer.Exit(code=2)` exits with code 2.
        raise typer.Exit(code=2)
    else:
        raise typer.Exit(code=0)


# =============================================================================
# Entry point guard
# =============================================================================
# CONCEPT: `if __name__ == "__main__":`
#   When Python runs a file directly (e.g., `python cli.py`), it sets the
#   special variable `__name__` to `"__main__"`. When the file is imported as
#   a module (e.g., `from flakydetect import cli`), `__name__` is set to
#   the module's name instead (e.g., `"flakydetect.cli"`).
#
#   This guard lets the file be BOTH importable (for testing and reuse)
#   AND directly runnable (for development).
#   It's a Python best practice to always include this in files that can
#   be run directly.
# =============================================================================
if __name__ == "__main__":
    app()
