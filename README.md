<div align="center">

<img src="docs/logo.svg" alt="Flaky Test Detector Logo" width="120" height="120"/>

# 🔬 Flaky Test Detector

**Find the tests you can't trust — before they find you.**

Run your test suite N times, catch inconsistent results, and get a ranked report of which tests are lying to you.

[![CI](https://github.com/ZachR-C/flaky-test-detector/actions/workflows/ci.yml/badge.svg)](https://github.com/ZachR-C/flaky-test-detector/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/flakydetect.svg)](https://badge.fury.io/py/flakydetect)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## The Problem

A **flaky test** is a test that sometimes passes and sometimes fails — with no code changes between runs.

You've seen this before:
- CI fails. You re-run it. It passes. You shrug and merge.
- Your test suite is red. You check the diff. Nothing changed.
- You start ignoring red builds because they're "probably just flaky."

This is how teams stop trusting their test suites. Flaky tests cost real engineering hours and mask real bugs.

**Flaky Test Detector (flakydetect)** solves this by running your test suite N times and telling you exactly which tests are inconsistent and how often they fail.

---

## Quick Start

```bash
# Install
pip install flakydetect

# Run your test suite 10 times and find the flakes
flaky-detect --cmd "pytest tests/" --runs 10
```

**Example output:**

```
🔬  flaky-detect v0.1.0
    Command:   pytest tests/
    Runs:      10

╭─────────────────────────────────────────────────────────────╮
│                      ⚠️  Flaky Tests                        │
├──────────────────────────────────┬────────────┬─────────────┤
│ Test Name                        │ Flake Rate │ Pass / Fail │
├──────────────────────────────────┼────────────┼─────────────┤
│ tests/test_auth.py::test_timeout │ 40.0%      │  6  /  4   │
│ tests/test_cache.py::test_race   │ 20.0%      │  8  /  2   │
│ tests/test_api.py::test_retry    │ 10.0%      │  9  /  1   │
╰──────────────────────────────────┴────────────┴─────────────╯

✅  Stable: 37/40 tests passed consistently.

╭────────────────────────────────╮
│  VERDICT: ISSUES FOUND         │
│  3 flaky tests | 0 broken      │
╰────────────────────────────────╯
```

---

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [All Options](#all-options)
  - [Examples](#examples)
  - [CI/CD Integration](#cicd-integration)
- [How It Works](#how-it-works)
- [Multi-Language Support](#multi-language-support)
- [Understanding the Output](#understanding-the-output)
  - [Flaky vs. Broken](#flaky-vs-broken)
  - [Flake Rate Formula](#flake-rate-formula)
- [Common Causes of Flaky Tests](#common-causes-of-flaky-tests)
- [Project Structure (for developers)](#project-structure-for-developers)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)

---

## Installation

**Requirements:** Python 3.8+

```bash
pip install flakydetect
```

Or with pipx (installs in isolated environment, keeps your global Python clean):

```bash
pipx install flakydetect
```

**From source** (for development):

```bash
git clone https://github.com/ZachR-C/flaky-test-detector.git
cd flaky-test-detector
pip install -e ".[dev]"   # -e = editable install, [dev] = includes dev tools
```

---

## Usage

### Basic Usage

```bash
# Run pytest 10 times (default)
flaky-detect --cmd "pytest tests/"

# Run 20 times for higher statistical confidence
flaky-detect --cmd "pytest tests/" --runs 20

# Save a JSON report
flaky-detect --cmd "pytest tests/" --runs 15 --output flaky-report.json

# Run in a specific directory
flaky-detect --cmd "pytest tests/" --runs 10 --dir /path/to/myproject
```

### All Options

```
Usage: flaky-detect [OPTIONS]

Options:
  -c, --cmd TEXT         The test command to run.           [required]
  -n, --runs INTEGER     Number of times to run. [1-1000]  [default: 10]
  -o, --output PATH      Save report as JSON to this path.
  -t, --threshold FLOAT  Min flake % to flag. [0.0-100.0]  [default: 5.0]
  -d, --dir PATH         Working directory for the command.
      --parser TEXT       Parser: auto|junit_xml|pytest_text [default: auto]
      --timeout INTEGER   Seconds per run before kill.       [default: 300]
  -v, --verbose          Show failure messages and debug info.
  -q, --quiet            Only show the final verdict.
      --version           Print version and exit.
  --help                  Show this message and exit.
```

### Examples

```bash
# Pytest with verbose output
flaky-detect --cmd "pytest tests/ -v" --runs 10

# Python's unittest module
flaky-detect --cmd "python -m unittest discover tests/" --runs 10 --parser pytest_text

# Java with JUnit (requires maven generating surefire XML)
flaky-detect --cmd "mvn test -q" --runs 10 --parser junit_xml

# Set a high threshold — only flag tests that flake more than 20% of the time
flaky-detect --cmd "pytest tests/" --runs 20 --threshold 20.0

# Quiet mode for CI — suppress all output, use exit code only
flaky-detect --cmd "pytest tests/" --runs 10 --quiet

# Full verbose output with failure messages
flaky-detect --cmd "pytest tests/" --runs 15 --verbose
```

### CI/CD Integration

**Exit codes:**

| Code | Meaning                                 |
|------|-----------------------------------------|
| `0`  | All tests stable — no issues found      |
| `1`  | Tool error (command failed to start, etc.) |
| `2`  | Flaky or always-failing tests found      |

Use this in GitHub Actions:

```yaml
# .github/workflows/flaky-check.yml
- name: Run flaky test detection
  run: |
    flaky-detect \
      --cmd "pytest tests/" \
      --runs 10 \
      --output flaky-report.json
  # Exit code 2 = flaky tests found. Whether to fail CI is up to you.
```

**Full reusable workflow:** See [`.github/workflows/flaky-check.yml`](.github/workflows/flaky-check.yml) — copy it into your own repo to add weekly flake detection.

---

## How It Works

The architecture is deliberately simple and extensible:

```
┌──────────────┐      ┌──────────────────┐      ┌─────────────┐      ┌──────────────┐
│  CLI (cli.py)│─────▶│ Runner (runner.py)│─────▶│  Parsers    │─────▶│  Aggregator  │
│              │      │                  │      │ (parsers/)  │      │(aggregator.py│
│  Parse args  │      │  Run command N   │      │             │      │              │
│  Set up logs │      │  times via       │      │ JUnit XML   │      │ Compute per- │
│  Orchestrate │      │  subprocess      │      │  ─or─       │      │ test stats   │
│  pipeline    │      │                  │      │ Pytest text │      │ (pass counts,│
└──────────────┘      │  Capture output, │      │             │      │ flake rates) │
                      │  exit codes,     │      │  Returns    │      └──────┬───────┘
                      │  timing          │      │  List of    │             │
                      └──────────────────┘      │ TestResult  │             ▼
                                                └─────────────┘      ┌──────────────┐
                                                                      │  Reporter    │
                                                                      │ (report.py)  │
                                                                      │              │
                                                                      │  Terminal    │
                                                                      │  output (rich│
                                                                      │  or plain)   │
                                                                      │  + JSON file │
                                                                      └──────────────┘
```

1. **Runner** — Executes your test command N times using Python's `subprocess` module. For pytest, it injects `--junitxml` to get structured XML output.

2. **Parsers** — Convert raw output into structured `TestResult` objects. The abstract `BaseParser` defines the interface; concrete implementations (`JUnitXMLParser`, `PytestTextParser`) handle specific formats.

3. **Aggregator** — Groups results by test name across all runs and computes statistics: pass count, fail count, flake rate, classification (flaky / broken / stable).

4. **Reporter** — Formats the final `FlakeReport` for terminal display (using `rich`) and JSON export.

---

## Multi-Language Support

Because we parse **JUnit XML** (a format supported by virtually every test framework), flakydetect supports multiple languages without language-specific parsers:

| Framework   | Language   | How to generate JUnit XML                     |
|-------------|------------|-----------------------------------------------|
| pytest      | Python     | Built-in: `pytest --junitxml=output.xml`     |
| unittest    | Python     | `pip install pytest` then run via pytest       |
| JUnit 4/5   | Java       | Built-in with Maven Surefire / Gradle          |
| TestNG      | Java       | Built-in                                       |
| GoogleTest  | C++        | `--gtest_output=xml:output.xml`               |
| CTest       | C/C++      | `ctest --output-on-failure -T test`           |
| jest        | JavaScript | `npm install jest-junit`, configure `reporters`|

---

## Understanding the Output

### Flaky vs. Broken

flakydetect distinguishes between two kinds of problem:

| Category       | Definition                              | What to do                    |
|----------------|-----------------------------------------|-------------------------------|
| ⚠️ **Flaky**   | Sometimes passes, sometimes fails        | Investigate; quarantine first |
| ❌ **Broken**   | Fails in EVERY run (never passes)        | Fix the bug — this is a real failure |
| ✅ **Stable**   | Passes in EVERY run                      | Nothing to do                 |

A **broken** test is not flaky — it's just failing. flakydetect reports it separately so you can tell the difference between "this test is unreliable" and "this test has a real bug."

### Flake Rate Formula

The flake rate for a test is computed as:

```
flake_rate = min(pass_count, fail_count) / total_runs
```

**Why `min()`?**  
We want to capture the "minority outcome" — the direction in which the test is inconsistent. A test that passes 8/10 times has the same degree of inconsistency as one that fails 8/10 times, but flipped. Taking the minimum of passes and failures gives the fraction of runs that were the "exception."

| pass | fail | total | formula       | rate  |
|------|------|-------|---------------|-------|
| 10   | 0    | 10    | min(10,0)/10  | 0.0%  |
| 9    | 1    | 10    | min(9,1)/10   | 10.0% |
| 7    | 3    | 10    | min(7,3)/10   | 30.0% |
| 5    | 5    | 10    | min(5,5)/10   | 50.0% |
| 0    | 10   | 10    | min(0,10)/10  | 0.0%  |

Note that 0% rate means either "always passing" OR "always failing" — use `is_always_failing` in the JSON output to tell the difference.

---

## Common Causes of Flaky Tests

Understanding WHY tests are flaky helps you fix them. Here are the most common causes with examples from the included `examples/demo_project/`:

### 1. Randomness without a fixed seed

```python
# ❌ Flaky: random value might be below 0.3
def test_score_is_high():
    score = get_random_score()
    assert score > 0.3

# ✅ Fixed: test the range, not a specific value
def test_score_is_valid():
    score = get_random_score()
    assert 0.0 <= score <= 1.0
```

**Fix:** Either mock the random function, set `random.seed(42)` before the test, or test properties rather than specific values.

### 2. Timing assumptions

```python
# ❌ Flaky: 30ms may not be enough on a slow CI runner
def test_background_task():
    task.start()
    time.sleep(0.03)
    assert task.result == expected  # May fail if task isn't done

# ✅ Fixed: wait for a signal, not a fixed time
def test_background_task():
    task.start()
    completed = task.wait(timeout=5.0)  # Uses threading.Event
    assert completed
    assert task.result == expected
```

**Fix:** Use synchronization primitives (`threading.Event`, `asyncio.Event`, `queue.Queue`) instead of fixed sleeps.

### 3. Shared mutable state between tests

```python
# ❌ Flaky: test_b is affected by test_a if test_a runs first
items = []  # Module-level mutable state

def test_a():
    items.append("hello")
    assert len(items) == 1

def test_b():
    assert len(items) == 0  # Fails if test_a ran first!

# ✅ Fixed: each test creates its own fresh state
def test_a():
    items = []
    items.append("hello")
    assert len(items) == 1

def test_b():
    items = []  # Fresh, independent list
    assert len(items) == 0
```

**Fix:** Avoid module-level mutable state. Use `@pytest.fixture` with `autouse=True` to reset shared state before each test.

### 4. Test order dependency

Similar to shared state — test B relies on test A having run first. pytest doesn't guarantee run order by default (and plugins like `pytest-randomly` actively randomize it).

**Fix:** Each test must set up its own preconditions. Use fixtures.

---

## Project Structure (for developers)

The codebase is organized around the **Separation of Concerns** principle — each module has one clearly defined job:

```
flaky-test-detector/
├── src/
│   └── flakydetect/
│       ├── __init__.py        # Package metadata and version
│       ├── cli.py             # CLI argument parsing and orchestration
│       ├── runner.py          # Execute test commands (subprocess)
│       ├── aggregator.py      # Combine run results into statistics
│       ├── report.py          # Format and output the final report
│       ├── models.py          # Data structures (TestResult, FlakeReport, etc.)
│       └── parsers/
│           ├── __init__.py    # Factory: get_parser() selects the right parser
│           ├── base.py        # Abstract base class (the interface contract)
│           ├── junit_xml.py   # Parses JUnit XML (Python, Java, C++, JS)
│           └── pytest_text.py # Parses pytest stdout (fallback)
├── tests/
│   ├── test_models.py         # Unit tests for data models
│   ├── test_parsers.py        # Unit tests for parsers
│   ├── test_aggregator.py     # Unit tests for the aggregation logic
│   └── fixtures/
│       └── sample_junit_output.xml
├── examples/
│   └── demo_project/
│       ├── test_stable.py         # Stable tests (should never flake)
│       ├── test_flaky_random.py   # Flaky due to randomness
│       └── test_flaky_sleep.py    # Flaky due to timing assumptions
├── .github/
│   └── workflows/
│       ├── ci.yml             # CI: lint + tests + type checking
│       └── flaky-check.yml    # Reusable workflow for users to copy
├── docs/
├── pyproject.toml             # Package config, dependencies, tool settings
└── README.md
```

**Adding a new parser** (e.g., for Mocha/JavaScript or Go's gotestsum):

1. Create `src/flakydetect/parsers/mocha_json.py`
2. Define a class that inherits from `BaseParser`
3. Implement the `parse()` method
4. Register it in `get_parser()` in `parsers/__init__.py`

That's it — no other files need to change.

---

## Contributing

Contributions are very welcome! This project is a great place to make your first open source contribution.

### Setup

```bash
git clone https://github.com/ZachR-C/flaky-test-detector.git
cd flaky-test-detector
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Running tests

```bash
pytest tests/ -v
```

### Running the linter

```bash
ruff check src/ tests/
black src/ tests/
```

### Good first issues

- Add a parser for a new test framework (Go's gotestsum, Mocha, Jest)
- Add an `--html` flag to generate an HTML report
- Add a `--badge` flag to generate a shields.io-compatible badge
- Improve the output formatting
- Add more examples to `examples/demo_project/`

---

## Roadmap

**v0.1.0 (current):**
- [x] Core run-N-times engine
- [x] JUnit XML parser (pytest, JUnit, GoogleTest)
- [x] pytest stdout fallback parser
- [x] Rich terminal output
- [x] JSON report export
- [x] CI exit codes
- [x] GitHub Actions integration examples

**v0.2.0 (planned):**
- [ ] Historical tracking (SQLite, track trends over time)
- [ ] HTML report generation
- [ ] Statistical confidence scoring (Wilson interval)
- [ ] `--badge` flag (generate a shields.io badge URL)
- [ ] Pre-commit hook integration

**v0.3.0 (planned):**
- [ ] Quarantine mode (`--quarantine` flag: skip known flaky tests in CI)
- [ ] GitHub PR comment integration
- [ ] Slack/webhook notifications

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Free for personal and commercial use. Attribution appreciated but not required.

---

<div align="center">

Built by [Zachary Cherney](https://github.com/ZachR-C) — a computer science student who got tired of spurious CI failures.

**If this saved you time, please ⭐ star the repo — it helps others find it.**

</div>
