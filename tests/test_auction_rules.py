"""Unit tests for the pure auction rules (no DB)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.enums import AuctionStatus, ExtensionTrigger
from app.services import auction_rules as rules

T0 = datetime(2030, 1, 15, 17, 0, tzinfo=timezone.utc)
CLOSE = T0.replace(hour=18)
FORCED = T0.replace(hour=18, minute=30)


def at(h: int, m: int, s: int = 0) -> datetime:
    return T0.replace(hour=h, minute=m, second=s)


def decide(trigger, now, before, after, close=CLOSE, forced=FORCED, x=10, y=5):
    return rules.evaluate_extension(
        trigger=trigger,
        now=now,
        current_close_at=close,
        forced_close_at=forced,
        window_minutes=x,
        extension_minutes=y,
        ranking_before=before,
        ranking_after=after,
    )


class TestStatus:
    @pytest.mark.parametrize(
        ("now", "close", "expected"),
        [
            (at(16, 59), CLOSE, AuctionStatus.SCHEDULED),
            (at(17, 0), CLOSE, AuctionStatus.ACTIVE),
            (at(17, 59, 59), CLOSE, AuctionStatus.ACTIVE),
            (at(18, 0), CLOSE, AuctionStatus.CLOSED),
            (at(18, 30), FORCED, AuctionStatus.FORCE_CLOSED),
            (at(18, 10), at(18, 5), AuctionStatus.CLOSED),
        ],
    )
    def test_compute_status(self, now, close, expected):
        assert (
            rules.compute_status(bid_start_at=T0, current_close_at=close, forced_close_at=FORCED, now=now)
            is expected
        )


class TestRanking:
    def test_lowest_total_first_then_earliest(self):
        entries = [
            rules.RankEntry(1, Decimal("100"), at(17, 5)),
            rules.RankEntry(2, Decimal("90"), at(17, 6)),
            rules.RankEntry(3, Decimal("100"), at(17, 1)),
        ]
        assert rules.rank_order(entries) == [2, 3, 1]

    def test_ranking_changed(self):
        assert rules.ranking_changed([], [1])  # first bid
        assert not rules.ranking_changed([1, 2], [1, 2])  # price drop without overtaking
        assert not rules.ranking_changed([1, 2], [1, 2, 3])  # newcomer at the bottom
        assert rules.ranking_changed([1, 2], [3, 1, 2])  # newcomer at the top pushes others
        assert rules.ranking_changed([1, 2, 3], [1, 3, 2])  # swap below L1

    def test_l1_changed(self):
        assert rules.l1_changed([], [1])
        assert not rules.l1_changed([1, 2, 3], [1, 3, 2])
        assert rules.l1_changed([1, 2], [2, 1])


class TestExtension:
    def test_window_boundaries(self):
        assert not rules.in_trigger_window(now=at(17, 49, 59), current_close_at=CLOSE, window_minutes=10)
        assert rules.in_trigger_window(now=at(17, 50), current_close_at=CLOSE, window_minutes=10)
        assert rules.in_trigger_window(now=at(17, 59, 59), current_close_at=CLOSE, window_minutes=10)
        assert not rules.in_trigger_window(now=at(18, 0), current_close_at=CLOSE, window_minutes=10)

    def test_bid_outside_window_does_not_extend(self):
        d = decide(ExtensionTrigger.BID_RECEIVED, at(17, 40), [1], [2, 1])
        assert not d.in_window and not d.triggered and not d.extended
        assert d.new_close_at == CLOSE

    def test_bid_received_extends_from_close_time_not_bid_time(self):
        d = decide(ExtensionTrigger.BID_RECEIVED, at(17, 55), [1], [1])
        assert d.extended
        assert d.new_close_at == at(18, 5)  # 6:00 -> 6:05 as in the spec
        assert "Bid received" in d.reason

    def test_any_rank_change_trigger(self):
        assert not decide(ExtensionTrigger.ANY_RANK_CHANGE, at(17, 58), [1, 2], [1, 2]).extended
        d = decide(ExtensionTrigger.ANY_RANK_CHANGE, at(17, 58), [1, 2], [2, 1])
        assert d.extended and "ranking changed" in d.reason

    def test_any_rank_change_below_l1(self):
        assert decide(ExtensionTrigger.ANY_RANK_CHANGE, at(17, 58), [1, 2, 3], [1, 3, 2]).extended

    def test_l1_trigger_ignores_changes_below_l1(self):
        assert not decide(ExtensionTrigger.L1_RANK_CHANGE, at(17, 59), [1, 2, 3], [1, 3, 2]).extended
        d = decide(ExtensionTrigger.L1_RANK_CHANGE, at(17, 59), [1, 2, 3], [3, 1, 2])
        assert d.extended and "L1" in d.reason

    def test_extension_capped_at_forced_close(self):
        d = decide(ExtensionTrigger.BID_RECEIVED, at(18, 27), [1], [1], close=at(18, 28))
        assert d.extended and d.capped_at_forced_close
        assert d.new_close_at == FORCED

    def test_no_extension_when_already_at_forced_close(self):
        d = decide(ExtensionTrigger.BID_RECEIVED, at(18, 29), [1], [1], close=FORCED)
        assert d.triggered and not d.extended
        assert d.new_close_at == FORCED

    def test_never_exceeds_forced_close_over_many_extensions(self):
        close = CLOSE
        for _ in range(50):
            d = decide(ExtensionTrigger.BID_RECEIVED, close - timedelta(seconds=1), [1], [1], close=close)
            close = d.new_close_at
            assert close <= FORCED
        assert close == FORCED
