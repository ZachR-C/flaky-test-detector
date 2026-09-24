# Contributing to Flaky Test Detector

Thank you for considering contributing! This document explains how to get set up,
the standards we follow, and how to submit changes.

---

## Getting Started

### 1. Fork and Clone

1. Click **Fork** on GitHub to create your own copy.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/flaky-test-detector.git
   cd flaky-test-detector
   ```

### 2. Set Up a Virtual Environment

A "virtual environment" is an isolated Python installation for this project —
it keeps dependencies separate from your system Python and from other projects.

```bash
# Create the virtual environment in a folder named .venv
python -m venv .venv

# Activate it (macOS/Linux)
source .venv/bin/activate

# Activate it (Windows)
.venv\Scripts\activate

# When activated, your prompt shows (.venv) at the beginning
# Install the package in "editable" mode + all dev dependencies
pip install -e ".[dev]"
```

**What is editable install (`-e`)?**  
`pip install -e .` installs the package in "editable" or "development" mode.
Instead of copying the source code into site-packages, it creates a link.
This means changes you make to the source are immediately reflected when you
import the package — no need to reinstall after every change.

### 3. Verify Setup

```bash
# Run the test suite — should show all passing
pytest tests/ -v

# Run the linter — should show no issues
ruff check src/ tests/

# Try the CLI
flaky-detect --help
```

---

## Making Changes

### 1. Create a Branch

Always work on a feature branch, never directly on `main`:

```bash
# Create and switch to a new branch
# Use a descriptive name: feature/html-report, fix/timeout-bug, docs/contributing
git checkout -b feature/your-feature-name
```

**Why branches?**  
Branches let multiple people work on different features simultaneously without
interfering with each other. When your feature is ready, you open a Pull Request
to merge it into `main`.

### 2. Write Your Code

A few guidelines:
- Follow the existing code style (Black-formatted, ruff-checked)
- Add inline comments explaining non-obvious decisions
- Follow the existing file patterns (`parsers/` for new parsers, etc.)

### 3. Write Tests

**Every new feature or bug fix should include a test.**

Tests go in `tests/`. Match the module you're testing:
- Changing `aggregator.py` → add tests to `tests/test_aggregator.py`
- Adding `parsers/mocha_json.py` → create `tests/test_parsers.py` or add to it

Run them:
```bash
pytest tests/ -v
```

Check coverage (what % of code the tests actually hit):
```bash
pytest tests/ --cov=src/flakydetect --cov-report=term-missing
```

### 4. Run All Quality Checks

Before opening a PR, make sure everything passes:

```bash
# Tests
pytest tests/ -v

# Linter
ruff check src/ tests/

# Formatter check (doesn't change files, just checks)
black --check src/ tests/

# Type checker
mypy src/flakydetect --ignore-missing-imports
```

### 5. Commit Your Changes

Write clear, descriptive commit messages:

```bash
# Good commit messages:
git commit -m "feat: add HTML report generation with --html flag"
git commit -m "fix: handle JUnit XML files with no testcase elements"
git commit -m "docs: add example for GoogleTest integration"

# Convention: feat: (new feature), fix: (bug fix), docs: (docs only),
#             test: (tests only), refactor: (code restructure, no feature change)
```

### 6. Open a Pull Request

1. Push your branch: `git push origin feature/your-feature-name`
2. Go to GitHub and click **New Pull Request**
3. Fill in the title (what you did) and description (why and how)
4. Wait for CI to pass (the automated checks run automatically)
5. Address any review feedback

---

## Good First Issues

If you're new to open source or this project, look for issues tagged
`good first issue` on GitHub. Some good starter areas:

- **Add a parser** for a new test framework (Mocha, Jest, Go's testing package)
- **Add a `--html` flag** to generate a self-contained HTML report
- **Add more demo examples** to `examples/demo_project/`
- **Improve error messages** for common mistakes
- **Write more tests** to increase coverage

---

## Code Standards

- **Style**: Formatted with [Black](https://black.readthedocs.io/) (line length 88)
- **Linting**: Checked with [ruff](https://docs.astral.sh/ruff/)
- **Type annotations**: All public functions should have type hints
- **Docstrings**: All public classes and methods should have docstrings
- **Tests**: New code should have accompanying tests

---

## Questions?

Open a GitHub Issue labeled `question`. There are no dumb questions.
