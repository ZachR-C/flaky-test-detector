# =============================================================================
# CHANGELOG.md
# =============================================================================
#
# CONCEPT: A Changelog
#   A changelog is a file that documents notable changes for each version.
#   It's important for open-source projects because it lets users know:
#     - What's new in this version?
#     - What was fixed?
#     - What changed that might break my existing usage?
#
# FORMAT: We follow "Keep a Changelog" (https://keepachangelog.com/)
#   - Unreleased: changes in main but not yet in a tagged release
#   - [version] - YYYY-MM-DD: each tagged release
#   - Categories: Added, Changed, Deprecated, Removed, Fixed, Security
#
# =============================================================================

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet (this is the initial release!)

---

## [0.1.0] - 2024-01-01

### Added
- Initial release 🎉
- Core run-N-times engine (`runner.py`) using subprocess
- JUnit XML parser (`parsers/junit_xml.py`) — works with pytest, JUnit, GoogleTest
- pytest stdout fallback parser (`parsers/pytest_text.py`)
- Flake rate aggregation (`aggregator.py`) with flaky/broken/stable classification
- Rich terminal output with colored tables and verdict panel
- JSON report export (`--output report.json`)
- CI-friendly exit codes (0 = clean, 2 = issues found)
- GitHub Actions workflow examples
- Demo flaky test examples (randomness, timing) with educational comments
- Comprehensive inline documentation throughout codebase

[Unreleased]: https://github.com/yourusername/flaky-test-detector/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/flaky-test-detector/releases/tag/v0.1.0
