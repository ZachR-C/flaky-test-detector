# =============================================================================
# examples/demo_project/test_stable.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   A set of "stable" tests — tests that should ALWAYS pass.
#   These are used as a baseline to show that flakydetect correctly identifies
#   healthy tests and does NOT falsely flag them as flaky.
#
# WHAT MAKES A STABLE TEST?
#   A stable test:
#     - Has no randomness
#     - Has no timing dependencies
#     - Has no dependency on external state (network, files, databases)
#     - Has no shared mutable state with other tests
#     - Is deterministic: the same inputs always produce the same outputs
#
# Run this demo with:
#   flaky-detect --cmd "pytest examples/demo_project/test_stable.py -v" --runs 5
#
# Expected output: 0 flaky tests detected.
#
# =============================================================================


def add(a, b):
    """A simple addition function. Always returns the same result for the same inputs."""
    return a + b


def multiply(a, b):
    """A simple multiplication function."""
    return a * b


def is_even(n):
    """Returns True if n is even, False if odd."""
    # `%` is the "modulo" operator: `n % 2` gives the remainder when dividing n by 2.
    # If the remainder is 0, the number is even.
    return n % 2 == 0


class Calculator:
    """
    A simple calculator class used for demonstration purposes.

    CONCEPT: Classes in the real world
      This Calculator class is a simple example of encapsulation —
      bundling related data (result) and behavior (add, subtract, reset)
      into a single object.
    """

    def __init__(self):
        # The running total starts at 0.
        self.result = 0

    def add(self, n):
        self.result += n
        return self  # Return self to allow method chaining: calc.add(5).add(3)

    def subtract(self, n):
        self.result -= n
        return self

    def reset(self):
        self.result = 0
        return self


# =============================================================================
# Stable tests — these should ALWAYS pass
# =============================================================================

class TestArithmetic:
    """Stable arithmetic tests with no external dependencies."""

    def test_addition(self):
        """Basic addition is deterministic."""
        assert add(2, 3) == 5

    def test_addition_with_negatives(self):
        """Addition works with negative numbers."""
        assert add(-1, 1) == 0
        assert add(-5, -3) == -8

    def test_multiplication(self):
        """Basic multiplication is deterministic."""
        assert multiply(4, 5) == 20
        assert multiply(0, 100) == 0

    def test_is_even_true_cases(self):
        """Even numbers are correctly identified."""
        assert is_even(0) is True
        assert is_even(2) is True
        assert is_even(100) is True
        assert is_even(-4) is True

    def test_is_even_false_cases(self):
        """Odd numbers are correctly identified as not even."""
        assert is_even(1) is False
        assert is_even(3) is False
        assert is_even(-7) is False


class TestCalculator:
    """Stable tests for the Calculator class."""

    def test_initial_result_is_zero(self):
        """A new Calculator starts at 0."""
        calc = Calculator()
        assert calc.result == 0

    def test_add_increases_result(self):
        """Adding a positive number increases result."""
        calc = Calculator()
        calc.add(5)
        assert calc.result == 5

    def test_multiple_adds(self):
        """Multiple additions accumulate correctly."""
        calc = Calculator()
        calc.add(3).add(7).add(10)
        assert calc.result == 20

    def test_subtract_decreases_result(self):
        """Subtraction decreases result."""
        calc = Calculator()
        calc.add(10).subtract(3)
        assert calc.result == 7

    def test_reset_returns_to_zero(self):
        """Reset brings result back to 0 regardless of previous operations."""
        calc = Calculator()
        calc.add(100).subtract(50).reset()
        assert calc.result == 0

    def test_instances_are_independent(self):
        """
        Two Calculator instances don't share state.

        This is an important property: each `Calculator()` call creates a
        brand new, independent object. Changes to one don't affect the other.

        CONCEPT: Instance variables vs class variables
          `self.result = 0` creates an INSTANCE variable — one per object.
          If it were `Calculator.result = 0` (class variable), all Calculator
          objects would share the same `result`. That would be a bug!
        """
        calc_a = Calculator()
        calc_b = Calculator()

        calc_a.add(99)
        # calc_b should still be 0 — it has its own independent `result`.
        assert calc_b.result == 0
