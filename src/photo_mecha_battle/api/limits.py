from __future__ import annotations

from dataclasses import dataclass

# docs/06 生成クォータ（確定）: 無課金 20/10、premium (generation_boost) 50/30。
# クォータ拡大は「生成の試行回数」のみを増やし、ステータス算出式・チーム編成・戦術スロット数/
# 条件/行動には影響しないため Pay to Convenience の範囲内（docs/06 公平性の整理）。
FREE_DAILY_CAPTURES = 20
FREE_DAILY_MECHS = 10
PREMIUM_DAILY_CAPTURES = 50
PREMIUM_DAILY_MECHS = 30

# docs/06 本仕様の正: クォータ拡大は generation_boost のみに紐づく（premium_tactics 等の
# 他 Entitlement では拡大しない）。
_QUOTA_BOOST_ENTITLEMENT_KEY = "generation_boost"


@dataclass(frozen=True)
class QuotaLimits:
    captures: int
    mechs: int


def limits_for_user(entitlements: list[dict[str, object]]) -> QuotaLimits:
    has_boost = any(
        item.get("key") == _QUOTA_BOOST_ENTITLEMENT_KEY and item.get("is_active")
        for item in entitlements
    )
    if has_boost:
        return QuotaLimits(captures=PREMIUM_DAILY_CAPTURES, mechs=PREMIUM_DAILY_MECHS)
    return QuotaLimits(captures=FREE_DAILY_CAPTURES, mechs=FREE_DAILY_MECHS)
