"""4D payout calculation service.

Values derived from the verified payout guide published by the reference interface.
All payouts are in test credits with no cash value.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

CENT = Decimal("0.01")


class BetType(StrEnum):
    BIG = "big"
    SMALL = "small"


class PrizeLevel(StrEnum):
    FIRST = "1st"
    SECOND = "2nd"
    THIRD = "3rd"
    STARTER = "starter"
    CONSOLATION = "consolation"


# Verified ordinary payouts (1 Big / 1 Small)
_ORDINARY: dict[tuple[BetType, PrizeLevel], Decimal] = {
    (BetType.BIG, PrizeLevel.FIRST): Decimal("4000.00"),
    (BetType.BIG, PrizeLevel.SECOND): Decimal("2000.00"),
    (BetType.BIG, PrizeLevel.THIRD): Decimal("1000.00"),
    (BetType.BIG, PrizeLevel.STARTER): Decimal("500.00"),
    (BetType.BIG, PrizeLevel.CONSOLATION): Decimal("150.00"),
    (BetType.SMALL, PrizeLevel.FIRST): Decimal("3000.00"),
    (BetType.SMALL, PrizeLevel.SECOND): Decimal("2000.00"),
    (BetType.SMALL, PrizeLevel.THIRD): Decimal("1000.00"),
    (BetType.SMALL, PrizeLevel.STARTER): Decimal("0.00"),
    (BetType.SMALL, PrizeLevel.CONSOLATION): Decimal("0.00"),
}

# k-Bet factors applied to the ordinary payout before permutation division
_KBET_FACTOR: dict[BetType, Decimal] = {
    BetType.BIG: Decimal("0.625"),       # 5/8
    BetType.SMALL: Decimal("10") / Decimal("7"),  # ≈1.428571, displayed as 1.429
}


def _round2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ordinary_payout(bet: BetType, prize: PrizeLevel) -> Decimal:
    """Return the verified ordinary payout for 1 Big or 1 Small."""
    return _ORDINARY[(bet, prize)]


def ibet_payout(bet: BetType, prize: PrizeLevel, permutations: int) -> Decimal:
    """i-Bet: ordinary payout divided by permutation count, rounded to 2 decimals."""
    base = _ORDINARY[(bet, prize)]
    return _round2(base / Decimal(permutations))


def kbet_payout(bet: BetType, prize: PrizeLevel, permutations: int) -> Decimal:
    """k-Bet: ordinary payout × k-Bet factor, then divided by permutations."""
    base = _ORDINARY[(bet, prize)]
    factor = _KBET_FACTOR[bet]
    return _round2((base * factor) / Decimal(permutations))