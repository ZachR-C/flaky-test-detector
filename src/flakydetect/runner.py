# =============================================================================
# flakydetect/runner.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   This module is responsible for actually RUNNING the test command.
#   It takes a shell command (like "pytest tests/"), runs it N times,
#   and captures the output and result of each run.
#
# CONCEPT: Separation of Concerns
#   Notice that this file does ONLY one thing — it runs commands and captures
#   their output. It doesn't parse the results or generate reports. That
#   happens in other modules. This design principle is called "Separation of
#   Concerns" and it makes code:
#     - Easier to test (you can test the runner without needing a real parser)
#     - Easier to understand (each file has one clear job)
#     - Easier to modify (changing the parser doesn't touch the runner)
#
# CONCEPT: Subprocess
#   When Python runs your test command, it doesn't run it "inside" Python.
#   Instead, Python launches a new, separate process (program) in the
#   operating system — just like opening a new terminal window and typing
#   the command yourself. That child process runs, produces output, and
#   returns an exit code. Python's `subprocess` module handles all of this.
#
# CONCEPT: Logging
#   Instead of using `print()` for diagnostic messages, professional code
#   uses a "logger." The logger lets you:
#     - Set different verbosity levels (DEBUG, INFO, WARNING, ERROR)
#     - Turn verbose output on/off without changing code
#     - Include timestamps and context automatically
#
# =============================================================================

# Standard library imports — these come built into Python, no installation needed.
import logging          # For diagnostic messages (not print statements)
import subprocess       # For launching the test command as a child process
import time             # For measuring how long each run takes
import tempfile         # For creating temporary files to store JUnit XML output
import os               # For file system operations (paths, checking if file exists)
from datetime import datetime  # For recording the timestamp of each run
from pathlib import Path       # Modern, readable way to work with file paths
from typing import Optional    # Optional[X] means the value is either X or None

# Local imports — these come from other files in our own package.
# The `.` prefix means "from the same package."
from .models import RunResult  # We return RunResult objects from this module
from .parsers import get_parser # Factory function to select the right parser

# CONCEPT: Logging Setup
#   `__name__` is a special Python variable that contains the current module's
#   name (e.g., "flakydetect.runner"). Using it as the logger name means log
#   messages will show which module they came from — very useful for debugging.
logger = logging.getLogger(__name__)


# =============================================================================
# TestRunner
# =============================================================================
# This class encapsulates all the logic for running a command multiple times
# and collecting the results.
#
# CONCEPT: Classes
#   A "class" is a blueprint for creating objects. An object bundles together:
#     - DATA (attributes): things the object KNOWS (e.g., the command to run)
#     - BEHAVIOR (methods): things the object can DO (e.g., run the command)
#
#   Example: A "Car" class might have:
#     - Attributes: color, make, model, speed
#     - Methods: accelerate(), brake(), honk()
#
#   Here, TestRunner knows:
#     - What command to run (`command`)
#     - How many times to run it (`num_runs`)
#     - Which directory to run it in (`working_dir`)
#   And it can:
#     - Run the suite N times (`run()`)
#     - Run the suite once (`_run_once()`)
# =============================================================================
class TestRunner:
    """
    Executes a test command multiple times and collects structured results.

    The runner is the "engine" of flakydetect. It knows nothing about what
    the tests are or what their results mean — it just runs the command,
    captures stdout/stderr, and hands the raw output off to a parser.

    Usage:
        runner = TestRunner(command="pytest tests/", num_runs=10)
        results = runner.run()  # returns a list of RunResult objects

    Args:
        command:     The shell command to run (e.g., "pytest tests/ --junitxml=...").
        num_runs:    How many times to execute the command.
        working_dir: The directory to run the command from. Defaults to the
                     current working directory.
        timeout:     Maximum seconds to allow a single run before killing it.
                     Prevents a hung process from stalling everything.
        parser_name: Which parser to use ("auto", "junit_xml", "pytest_text").
    """

    # `__init__` is the "constructor" — it runs when you create a new
    # TestRunner object. Its job is to set up the object's initial state
    # by storing all the configuration values as attributes (`self.xxx`).
    def __init__(
        self,
        command: str,
        num_runs: int,
        working_dir: Optional[str] = None,   # type: ignore[name-defined]
        timeout: Optional[int] = 300,          # type: ignore[name-defined]
        parser_name: str = "auto",
    ) -> None:
        # `self` refers to the object being created.
        # `self.command = command` stores the command string ON the object.
        self.command = command
        self.num_runs = num_runs

        # If no working directory is given, use the current directory.
        # `os.getcwd()` returns the current working directory as a string.
        self.working_dir = working_dir or os.getcwd()

        self.timeout = timeout
        self.parser_name = parser_name

        # We'll store all the RunResult objects here as we go.
        # Starting with an empty list that we'll append to.
        self._results: list = []

        logger.debug(
            "TestRunner initialized: command=%r, num_runs=%d, working_dir=%r",
            self.command,
            self.num_runs,
            self.working_dir,
        )

    # -------------------------------------------------------------------------
    # run()
    # -------------------------------------------------------------------------
    # This is the main public method of the class. It loops N times,
    # running the test command each time, and returns all the results.
    # -------------------------------------------------------------------------
    def run(self) -> list:
        """
        Run the test command `num_runs` times and return a list of RunResults.

        This is the primary entry point for the runner. It orchestrates
        the overall loop, handles per-run errors gracefully, and logs
        progress as it goes.

        Returns:
            A list of RunResult objects, one per successful run.
            If a run crashes badly (e.g., the command is not found),
            we log the error and continue to the next run.
        """
        # Reset results in case run() is called more than once on the same object.
        self._results = []

        # Log that we're starting — this shows up when the user runs with --verbose.
        logger.info(
            "Starting %d run(s) of command: %s", self.num_runs, self.command
        )

        # CONCEPT: for loop
        #   `for i in range(1, self.num_runs + 1):` counts from 1 to num_runs
        #   (inclusive). For example, if num_runs=3, i takes values 1, 2, 3.
        #
        #   `range(start, stop)` generates numbers from `start` up to but
        #   NOT including `stop`. So `range(1, 4)` gives 1, 2, 3.
        for run_index in range(1, self.num_runs + 1):
            logger.info(
                "Run %d/%d ...", run_index, self.num_runs
            )

            # CONCEPT: try / except
            #   Code inside `try:` is attempted. If ANY line raises an
            #   exception (error), Python jumps to the `except:` block
            #   instead of crashing the whole program.
            #
            #   `Exception as e` captures the exception object so we
            #   can inspect its message.
            try:
                # Run the command once and get a RunResult back.
                result = self._run_once(run_index)
                self._results.append(result)

                logger.info(
                    "Run %d/%d complete: %d passed, %d failed (exit code %d)",
                    run_index,
                    self.num_runs,
                    result.passed_count,
                    result.failed_count,
                    result.exit_code,
                )

            except Exception as e:
                # Something unexpected went wrong (e.g., command not found,
                # permission denied, etc.). Log the error and keep going.
                logger.error(
                    "Run %d/%d raised an unexpected error: %s",
                    run_index, self.num_runs, e,
                    exc_info=True,  # Also log the full traceback
                )
                # `continue` skips to the next loop iteration.
                continue

        logger.info(
            "All runs complete. %d/%d runs succeeded.",
            len(self._results),
            self.num_runs,
        )

        # Return the list we've been building up.
        return self._results

    # -------------------------------------------------------------------------
    # _run_once()
    # -------------------------------------------------------------------------
    # The underscore prefix `_run_once` signals that this is a "private" method.
    # CONCEPT: Public vs Private methods
    #   Public methods (no underscore) are part of the class's "API" — they're
    #   meant to be called by outside code. Private methods (leading underscore)
    #   are implementation details — internal helpers not meant for direct use.
    #
    #   Python doesn't ENFORCE this (you can still call `runner._run_once()`),
    #   but the underscore is a convention that says "this is an internal detail,
    #   don't rely on it staying the same."
    # -------------------------------------------------------------------------
    def _run_once(self, run_index: int) -> RunResult:
        """
        Execute the test command once and return a RunResult.

        This method:
          1. Creates a temporary file to receive JUnit XML output.
          2. Injects `--junitxml=<path>` into the command (if using pytest).
          3. Runs the command using subprocess.
          4. Reads the JUnit XML output and parses it.
          5. Cleans up the temporary file.
          6. Returns a RunResult.

        Args:
            run_index: Which run number this is (1-based).

        Returns:
            A RunResult containing all parsed test outcomes for this run.

        Raises:
            RuntimeError: If the command cannot be started at all
                          (e.g., executable not found).
        """
        # Record the timestamp at which this run started.
        # `datetime.now()` gives the current local date and time.
        start_time = datetime.now()

        # CONCEPT: Context Manager / `with` statement
        #   `with tempfile.NamedTemporaryFile(...) as tmp:` creates a temporary
        #   file and automatically deletes it when the `with` block exits —
        #   even if an exception is raised. This is the "context manager" pattern.
        #
        #   Without `with`, you'd have to manually call `tmp.close()` and
        #   `os.unlink(tmp.name)` in a `finally:` block, which is messy.
        #
        #   `delete=False` means we DON'T delete when the file closes —
        #   we manage deletion ourselves after reading the content.
        #   `suffix=".xml"` gives the file a .xml extension.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".xml",
            delete=False,
            dir=self.working_dir,
        ) as tmp:
            xml_path = tmp.name  # Save the file path for later use

        # Build the actual command to run.
        # We inject `--junitxml=<path>` so pytest writes structured XML output
        # that we can parse reliably (rather than scraping colored terminal text).
        actual_command = self._build_command(xml_path)

        logger.debug("Executing: %s", actual_command)

        # Measure how long the run takes using `time.monotonic()`.
        # CONCEPT: Monotonic Clock
        #   `time.monotonic()` returns a float representing seconds since an
        #   arbitrary fixed point. "Monotonic" means it only ever increases —
        #   it won't jump backward if the system clock is adjusted. This makes
        #   it perfect for timing durations (as opposed to getting the actual
        #   current time, for which you'd use `datetime.now()`).
        run_start = time.monotonic()

        try:
            # `subprocess.run()` is Python's way of launching an external command.
            # Arguments explained:
            #   actual_command:  The command string to run.
            #   shell=True:      Run through the system shell (bash/cmd), which
            #                    allows things like pipes (|) and redirects (>).
            #   capture_output:  Capture stdout and stderr instead of printing them.
            #   text=True:       Decode stdout/stderr as text (not raw bytes).
            #   cwd:             The directory to run the command from.
            #   timeout:         Kill the process if it runs longer than this (seconds).
            proc = subprocess.run(
                actual_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=self.timeout,
            )

        except subprocess.TimeoutExpired:
            # The run took longer than `self.timeout` seconds — we killed it.
            # Log an error and re-raise so the caller can handle it.
            duration = time.monotonic() - run_start
            logger.error(
                "Run %d timed out after %.1fs (limit: %ds)",
                run_index, duration, self.timeout,
            )
            # Re-raise with more context
            raise RuntimeError(
                f"Run {run_index} timed out after {self.timeout}s"
            )

        except FileNotFoundError:
            # The command executable wasn't found on the system PATH.
            raise RuntimeError(
                f"Command not found. Make sure the test runner is installed "
                f"and available in your PATH.\nCommand: {self.command}"
            )

        # Calculate wall-clock duration of the run.
        duration = time.monotonic() - run_start

        logger.debug(
            "Run %d exited with code %d in %.2fs",
            run_index, proc.returncode, duration,
        )
        logger.debug("stdout:\n%s", proc.stdout[:500] if proc.stdout else "(empty)")

        # -----------------------------------------------------------------------
        # Parse the test output
        # -----------------------------------------------------------------------
        # Select and use the right parser to turn raw output into TestResult objects.
        parser = get_parser(
            parser_name=self.parser_name,
            xml_path=xml_path,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

        test_results = parser.parse()

        # Clean up the temporary XML file now that we've read it.
        # `Path(xml_path).unlink(missing_ok=True)` deletes the file.
        # `missing_ok=True` means "don't raise an error if the file doesn't exist."
        Path(xml_path).unlink(missing_ok=True)

        # Build and return the RunResult object.
        return RunResult(
            run_index=run_index,
            tests=test_results,
            exit_code=proc.returncode,
            duration=duration,
            timestamp=start_time,
        )

    def _build_command(self, xml_output_path: str) -> str:
        """
        Build the final command string to execute.

        If the user's command contains "pytest" and doesn't already have
        a --junitxml flag, we inject one so pytest writes structured XML output.
        If the command isn't pytest (e.g., it's a custom script), we run it as-is
        and fall back to parsing stdout.

        Args:
            xml_output_path: The path to the temporary XML file to write to.

        Returns:
            The final shell command string.
        """
        # Check whether the command is a pytest invocation.
        # `in` checks if a substring exists within a string.
        # We check both "pytest" and "python -m pytest" (two common ways to run pytest).
        is_pytest = "pytest" in self.command

        if is_pytest and "--junitxml" not in self.command:
            # Inject the --junitxml flag so pytest produces structured output.
            # We also add -p no:cacheprovider to disable the cache plugin,
            # which can interfere with repeated runs.
            injected = f" --junitxml={xml_output_path} -p no:cacheprovider"
            return self.command + injected

        # For non-pytest commands, run as-is and rely on stdout parsing.
        return self.command



