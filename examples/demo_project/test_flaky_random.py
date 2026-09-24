# =============================================================================
# examples/demo_project/test_flaky_random.py
# =============================================================================
#
# PURPOSE OF THIS FILE:
#   Demonstrates tests that are flaky due to RANDOMNESS.
#
# WHY DO TESTS FAIL DUE TO RANDOMNESS?
#   Some code uses random numbers — for shuffling, generating IDs, sampling
#   data, making probabilistic decisions, etc. If a test doesn't control the
#   random seed, it may pass MOST of the time but fail occasionally when
#   the random values happen to hit an edge case.
#
# REAL-WORLD EXAMPLES OF THIS BUG PATTERN:
#   - A test asserts the first item of a shuffled list is a specific value
#   - A test assumes a randomly-generated ID will be unique (birthday paradox)
#   - A test runs a function that relies on random.choice and doesn't mock it
#   - A function with a "small" probability of an edge case (like < 1% chance)
#     that the test exposes when it's triggered
#
# HOW TO FIX THIS (not done here, since we WANT flakiness):
#   Fix #1 (Seeding): Set `random.seed(42)` before the test so the sequence
#           is deterministic. Same seed → same random values every time.
#   Fix #2 (Mocking): Use `unittest.mock.patch('random.random', return_value=0.5)`
#           to replace the random function with a predictable one.
#   Fix #3 (Redesign): Restructure the test so it doesn't depend on specific
#           random values — test the property instead of the value.
#
# Run this demo with:
#   flaky-detect --cmd "pytest examples/demo_project/test_flaky_random.py -v" --runs 20
#
# Expected output: Several flaky tests detected with varying flake rates.
#
# =============================================================================

import random
import string

# We do NOT set `random.seed()` here — that's intentional.
# Without a fixed seed, `random.random()` produces different values each run.


# =============================================================================
# The code being tested (the "production code")
# =============================================================================

def get_random_score() -> float:
    """
    Returns a "score" between 0.0 and 1.0.

    In real code, this might represent a machine learning confidence score,
    a quality metric, or some other probabilistic value.
    """
    return random.random()  # Uniformly random between 0.0 and 1.0


def pick_winner(candidates: list) -> str:
    """
    Randomly selects a winner from a list of candidates.
    In real code: could be A/B testing, load balancing, random sampling, etc.
    """
    if not candidates:
        raise ValueError("Cannot pick from empty list")
    return random.choice(candidates)


def generate_short_id(length: int = 4) -> str:
    """
    Generates a short random alphanumeric ID.
    In real code: session tokens, URL slugs, temporary codes, etc.
    """
    # `random.choices()` picks `length` characters with replacement from the alphabet.
    # `string.ascii_letters` = "abcdefghijklmnopqrstuvwxyzABCDE..."
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def maybe_fail_operation(failure_probability: float = 0.3) -> bool:
    """
    Simulates a real-world operation that sometimes fails.
    In real code: network calls, disk I/O, external APIs — all have failure rates.

    Returns True on success, raises RuntimeError on failure.
    """
    if random.random() < failure_probability:
        raise RuntimeError("Operation failed (simulated failure)")
    return True


# =============================================================================
# Flaky tests — will sometimes pass, sometimes fail
# =============================================================================

class TestRandomFlakiness:
    """
    These tests are INTENTIONALLY FLAKY to demonstrate the problem.

    DO NOT write tests like this in real code.
    Each test here has an annotation explaining the exact flaw.
    """

    def test_score_is_high_enough(self):
        """
        FLAW: Asserts a random value exceeds an arbitrary threshold.
        This passes ~70% of the time and fails ~30% of the time.
        Flake rate: ~30%
        """
        score = get_random_score()
        # This will fail whenever `score` is below 0.3 (30% of the time).
        assert score > 0.3, f"Score too low: {score:.3f}"

    def test_winner_is_alice(self):
        """
        FLAW: Asserts a specific random outcome.
        With 3 candidates, Alice wins only 1/3 of the time.
        Flake rate: ~67%
        """
        candidates = ["Alice", "Bob", "Charlie"]
        winner = pick_winner(candidates)
        # This only passes when "Alice" is randomly selected (1 in 3 chance).
        assert winner == "Alice", f"Expected Alice to win, got {winner}"

    def test_id_starts_with_letter(self):
        """
        FLAW: Assumes randomness will produce a specific character type.
        With digits mixed in, there's ~38% chance the first character is a digit.
        Flake rate: ~38%
        """
        short_id = generate_short_id(length=4)
        # `string.ascii_letters` contains only letters (no digits).
        # The ID could start with a digit ~38% of the time.
        assert short_id[0] in string.ascii_letters, (
            f"ID '{short_id}' starts with a digit, not a letter"
        )

    def test_operation_succeeds(self):
        """
        FLAW: Assumes a probabilistic operation will succeed.
        The operation fails 30% of the time.
        Flake rate: ~30%
        """
        # We expect this NOT to raise an exception.
        # But it WILL raise RuntimeError 30% of the time.
        result = maybe_fail_operation(failure_probability=0.3)
        assert result is True

    def test_two_ids_are_different(self):
        """
        FLAW: Assumes random values will never collide (Birthday Paradox).
        With a 4-character alphanumeric ID (62^4 = ~14.7M possibilities),
        collisions are rare but non-zero.
        Flake rate: very low but non-zero (demonstrates subtle flakiness)
        """
        id_1 = generate_short_id(length=4)
        id_2 = generate_short_id(length=4)
        assert id_1 != id_2, (
            f"Generated duplicate ID: {id_1!r}  (extremely rare but possible!)"
        )


# =============================================================================
# Fixed versions of the same tests (for comparison)
# =============================================================================
# These show how the SAME tests could be written correctly.
# They should ALWAYS pass because they don't depend on specific random values.

class TestProperlyWrittenRandomTests:
    """
    These tests cover the same code but are NOT flaky.
    They test PROPERTIES of the output rather than specific random values.
    """

    def test_score_is_in_valid_range(self):
        """
        CORRECT: Tests that the score is within its valid range (0.0 to 1.0).
        This ALWAYS passes because any random.random() value is in [0.0, 1.0).
        """
        score = get_random_score()
        # We don't care about the specific value — just that it's valid.
        assert 0.0 <= score < 1.0, f"Score out of range: {score}"

    def test_winner_is_from_candidates(self):
        """
        CORRECT: Tests that the winner is one of the valid candidates.
        This ALWAYS passes because random.choice() always picks from the list.
        """
        candidates = ["Alice", "Bob", "Charlie"]
        winner = pick_winner(candidates)
        assert winner in candidates, f"Winner {winner!r} not in candidates list"

    def test_id_has_correct_length(self):
        """
        CORRECT: Tests the structure of the output, not its random content.
        A 4-character ID always has length 4.
        """
        short_id = generate_short_id(length=4)
        assert len(short_id) == 4

    def test_id_contains_only_valid_characters(self):
        """
        CORRECT: Tests that the ID only contains expected character types.
        `all(c in alphabet for c in short_id)` checks every character.
        """
        alphabet = set(string.ascii_letters + string.digits)
        short_id = generate_short_id(length=8)
        assert all(c in alphabet for c in short_id), (
            f"ID contains unexpected characters: {short_id!r}"
        )

    def test_empty_candidates_raises_error(self):
        """
        CORRECT: Tests error handling — always deterministic because it tests
        the error path, not the random path.
        """
        import pytest
        with pytest.raises(ValueError, match="empty list"):
            pick_winner([])
