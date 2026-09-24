# =============================================================================
# flakydetect/__init__.py
# =============================================================================
#
# This file is the "package initializer" for the flakydetect package.
#
# CONCEPT: What is a Python Package?
#   A "package" in Python is just a folder that contains Python files.
#   The special file `__init__.py` (pronounced "dunder init") tells Python:
#   "this folder is a package — treat it like a importable module."
#
#   Without this file, Python would not recognize the folder as a package
#   and you wouldn't be able to do: `from flakydetect import ...`
#
# CONCEPT: What is a Version Number?
#   Software versions follow a convention called "Semantic Versioning" (SemVer):
#     MAJOR.MINOR.PATCH  →  e.g., "0.1.0"
#     - MAJOR: big breaking changes (0 means "not stable/released yet")
#     - MINOR: new features added in a backwards-compatible way
#     - PATCH: bug fixes
#
# WHY EXPOSE THESE HERE?
#   Putting the version number here makes it the "single source of truth."
#   Instead of having the version written in 5 different files (and getting
#   out of sync), everything imports it from one place.
#
# =============================================================================

# The version of this package.
# We start at "0.1.0" because the tool is new and not yet considered "stable."
# When you publish to PyPI or tag a GitHub release, this is the number you use.
__version__ = "0.1.0"

# The name of this package, exposed as a public attribute.
__author__ = "Your Name"
__email__ = "you@example.com"
__license__ = "MIT"
