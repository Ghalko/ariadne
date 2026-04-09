from __future__ import annotations


def plan_price(plan_code: str) -> int:
    prices = {"starter": 1900, "growth": 4900}
    return prices[plan_code]
