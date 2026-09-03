"""Deterministic low-discrepancy sampling shared by trajectory callers."""
from __future__ import annotations

from functools import lru_cache


_PRIMES = (2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,
           73,79,83,89,97,101,103,107,109,113,127,131,137,139,149,151,
           157,163,167,173,179,181,191,193,197,199,211,223,227,229)


def _radical_inverse(n: int, base: int) -> float:
    inv = 1.0 / base
    factor = inv
    out = 0.0
    while n:
        n, digit = divmod(n, base)
        out += digit * factor
        factor *= inv
    return out


@lru_cache(maxsize=128)
def sample_dimension(samples: int, dim: int) -> tuple[float, ...]:
    """Return one deterministic dimension, reusable across workload shapes."""
    samples = max(1, int(samples))
    base = _PRIMES[dim % len(_PRIMES)]
    return tuple(_radical_inverse(i + 1, base) for i in range(samples))


@lru_cache(maxsize=32)
def sample_coordinates(samples: int, dimensions: int) -> tuple[tuple[float, ...], ...]:
    """Return cached deterministic coordinate rows shared by all roles."""
    samples = max(1, int(samples))
    dimensions = max(1, int(dimensions))
    columns = tuple(sample_dimension(samples, dim) for dim in range(dimensions))
    return tuple(
        tuple(columns[dim][scenario] for dim in range(dimensions))
        for scenario in range(samples)
    )


def reset_sampling_cache() -> None:
    """Clear process-local sampling memoization for isolated engine runs/tests."""
    sample_dimension.cache_clear()
    sample_coordinates.cache_clear()
