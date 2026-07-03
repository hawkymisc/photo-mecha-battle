from __future__ import annotations

from dataclasses import dataclass

# docs/06 Pay to Win回避原則: 課金は保存枠・要約・装飾・戦術コンパイル導線に限定し、
# 撮影・メカ生成の日次上限（不正対策）は課金状態に関わらず全員共通とする。
FREE_DAILY_CAPTURES = 20
FREE_DAILY_MECHS = 10


@dataclass(frozen=True)
class QuotaLimits:
    captures: int
    mechs: int


def limits_for_user(entitlements: list[dict[str, object]]) -> QuotaLimits:
    del entitlements  # anti-abuse quotas are identical for every user regardless of billing status
    return QuotaLimits(captures=FREE_DAILY_CAPTURES, mechs=FREE_DAILY_MECHS)
