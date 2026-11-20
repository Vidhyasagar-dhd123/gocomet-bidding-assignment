from app.services.closer import close_due_auctions
from tests.conftest import API, iso


async def test_closer_finalises_due_auctions(make_rfq, make_supplier, bid, client, clock, session_factory):
    normal = await make_rfq(name="Normal")
    forced = await make_rfq(name="Forced", bid_close_at=iso(clock().replace(hour=18, minute=28)))
    open_ = await make_rfq(name="Still open", bid_close_at=iso(clock().replace(hour=19)),
                           forced_close_at=iso(clock().replace(hour=20)))
    a, b = await make_supplier("Alpha"), await make_supplier("Beta")
    await bid(normal["id"], a["id"], 1000)
    await bid(normal["id"], b["id"], 900)
    clock.set(clock().replace(hour=18, minute=27))
    await bid(forced["id"], a["id"], 700)  # 18:28 -> capped at 18:30

    clock.set(clock().replace(hour=18, minute=31))
    async with session_factory() as db:
        events = await close_due_auctions(db, now=clock())
    by_rfq = {e.rfq_id: e for e in events}
    assert set(by_rfq) == {normal["id"], forced["id"]}
    assert by_rfq[normal["id"]].event_type.value == "AUCTION_CLOSED"
    assert by_rfq[normal["id"]].details["winning_supplier"] == "Beta"
    assert by_rfq[forced["id"]].event_type.value == "AUCTION_FORCE_CLOSED"

    # Idempotent: a second sweep does nothing.
    async with session_factory() as db:
        assert await close_due_auctions(db, now=clock()) == []

    detail = (await client.get(f"{API}/rfqs/{normal['id']}")).json()
    assert detail["status"] == "CLOSED"
    assert detail["closed_at"].startswith("2030-01-15T18:00:00")
    assert detail["activity"][0]["event_type"] == "AUCTION_CLOSED"
    assert "L1: Beta at 900" in detail["activity"][0]["message"]

    still_open = (await client.get(f"{API}/rfqs/{open_['id']}")).json()
    assert still_open["status"] == "ACTIVE" and still_open["closed_at"] is None


async def test_closer_handles_auction_without_bids(make_rfq, clock, session_factory):
    await make_rfq()
    clock.set(clock().replace(hour=18, minute=1))
    async with session_factory() as db:
        events = await close_due_auctions(db, now=clock())
    assert len(events) == 1
    assert "no bids received" in events[0].message
