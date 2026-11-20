import asyncio
import json
from datetime import datetime, timedelta

from tests.conftest import API, iso


async def _detail(client, rfq_id):
    return (await client.get(f"{API}/rfqs/{rfq_id}")).json()


async def test_ranking_and_quote_details(make_rfq, make_supplier, bid, client):
    rfq = await make_rfq()
    a = await make_supplier("Alpha")
    b = await make_supplier("Beta")
    c = await make_supplier("Gamma")

    await bid(rfq["id"], a["id"], 1000, origin_charges=50, destination_charges=25, carrier_name="MSC")
    await bid(rfq["id"], b["id"], 950)
    res = await bid(rfq["id"], c["id"], 1200)
    assert res["rank_label"] == "L3"
    res = await bid(rfq["id"], a["id"], 900, origin_charges=50, destination_charges=25)  # total 975 -> L2
    assert res["rank"] == 2 and res["bid"]["total_amount"] == 975

    detail = await _detail(client, rfq["id"])
    ranking = detail["ranking"]
    assert [(r["rank_label"], r["bid"]["supplier_name"], r["bid"]["total_amount"]) for r in ranking] == [
        ("L1", "Beta", 950),
        ("L2", "Alpha", 975),
        ("L3", "Gamma", 1200),
    ]
    alpha = ranking[1]
    assert alpha["bid_count"] == 2
    assert alpha["bid"]["carrier_name"] == "Maersk"  # standing bid = latest re-bid
    assert alpha["bid"]["origin_charges"] == 50 and alpha["bid"]["destination_charges"] == 25
    assert alpha["bid"]["transit_time_days"] == 20
    assert "quote_validity_date" in alpha["bid"]
    assert detail["lowest_bid"] == 950

    history = (await client.get(f"{API}/rfqs/{rfq['id']}/bids")).json()
    assert [h["total_amount"] for h in history] == [950, 975, 1075, 1200]


async def test_rebid_must_be_lower(make_rfq, make_supplier, bid):
    rfq = await make_rfq()
    a = await make_supplier("Alpha")
    await bid(rfq["id"], a["id"], 1000)
    err = await bid(rfq["id"], a["id"], 1000, expect=422)
    assert "must be lower" in err["error"]["message"]
    await bid(rfq["id"], a["id"], 1100, expect=422)
    await bid(rfq["id"], a["id"], 999.99)


async def test_bid_validation(make_rfq, make_supplier, bid, clock):
    rfq = await make_rfq()
    a = await make_supplier("Alpha")
    await bid(rfq["id"], a["id"], 0, expect=422)
    await bid(rfq["id"], a["id"], -5, expect=422)
    await bid(rfq["id"], a["id"], 100, transit_time_days=0, expect=422)
    await bid(rfq["id"], a["id"], 100, expect=422, quote_validity_date=(clock() - timedelta(days=1)).date().isoformat())
    await bid(rfq["id"], 999, 100, expect=404)
    await bid(999, a["id"], 100, expect=404)


async def test_cannot_bid_before_start_or_after_close(make_rfq, make_supplier, bid, clock):
    rfq = await make_rfq(bid_start_at=iso(clock() + timedelta(minutes=10)))
    a = await make_supplier("Alpha")
    err = await bid(rfq["id"], a["id"], 100, expect=409)
    assert err["error"]["code"] == "auction_not_open"

    clock.advance(minutes=10)
    await bid(rfq["id"], a["id"], 100)

    clock.set(clock().replace(hour=18, minute=0))
    err = await bid(rfq["id"], a["id"], 90, expect=409)
    assert err["error"]["message"] == "Auction is closed"


async def test_bid_received_trigger_extends_and_logs_reason(make_rfq, make_supplier, bid, client, clock):
    rfq = await make_rfq()  # close 18:00, forced 18:30, X=10, Y=5
    a = await make_supplier("Alpha")

    clock.set(clock().replace(hour=17, minute=45))  # outside window
    res = await bid(rfq["id"], a["id"], 1000)
    assert res["auction_extended"] is False

    clock.set(clock().replace(hour=17, minute=55))  # inside window
    res = await bid(rfq["id"], a["id"], 990)
    assert res["auction_extended"] is True
    assert res["current_close_at"].startswith("2030-01-15T18:05:00")
    assert "Bid received" in res["extension_reason"]

    detail = await _detail(client, rfq["id"])
    assert detail["extension_count"] == 1
    assert detail["bid_close_at"].startswith("2030-01-15T18:00:00")  # original stays
    ext = [e for e in detail["activity"] if e["event_type"] == "AUCTION_EXTENDED"]
    assert len(ext) == 1
    assert ext[0]["details"]["previous_close_at"].startswith("2030-01-15T18:00:00")
    assert ext[0]["details"]["new_close_at"].startswith("2030-01-15T18:05:00")
    assert ext[0]["details"]["trigger"] == "BID_RECEIVED"
    assert "Bid received" in ext[0]["details"]["reason"]

    # The window now follows the new close time (17:55 - 18:05).
    clock.set(clock().replace(hour=18, minute=2))
    res = await bid(rfq["id"], a["id"], 980)
    assert res["auction_extended"] and res["current_close_at"].startswith("2030-01-15T18:10:00")


async def test_any_rank_change_trigger(make_rfq, make_supplier, bid, clock):
    rfq = await make_rfq(extension_trigger="ANY_RANK_CHANGE")
    a, b, c = await make_supplier("Sup A"), await make_supplier("Sup B"), await make_supplier("Sup C")
    await bid(rfq["id"], a["id"], 1000)
    await bid(rfq["id"], b["id"], 1100)

    clock.set(clock().replace(hour=17, minute=56))
    res = await bid(rfq["id"], b["id"], 1050)  # still L2: no rank change
    assert res["auction_extended"] is False
    res = await bid(rfq["id"], c["id"], 1200)  # newcomer at the bottom: no one moved
    assert res["auction_extended"] is False

    clock.set(clock().replace(hour=17, minute=58))
    res = await bid(rfq["id"], c["id"], 1040)  # C overtakes B (L3 -> L2)
    assert res["auction_extended"] is True
    assert "ranking changed" in res["extension_reason"]


async def test_l1_trigger_only_extends_on_new_lowest_bidder(make_rfq, make_supplier, bid, clock):
    rfq = await make_rfq(extension_trigger="L1_RANK_CHANGE")
    a, b, c = await make_supplier("Sup A"), await make_supplier("Sup B"), await make_supplier("Sup C")
    await bid(rfq["id"], a["id"], 1000)
    await bid(rfq["id"], b["id"], 1100)
    await bid(rfq["id"], c["id"], 1200)

    clock.set(clock().replace(hour=17, minute=55))
    res = await bid(rfq["id"], c["id"], 1050)  # C overtakes B but not L1
    assert res["auction_extended"] is False
    res = await bid(rfq["id"], a["id"], 990)  # L1 lowers own price, still L1
    assert res["auction_extended"] is False

    clock.set(clock().replace(hour=17, minute=59))
    res = await bid(rfq["id"], c["id"], 980)  # C becomes L1
    assert res["auction_extended"] is True
    assert res["current_close_at"].startswith("2030-01-15T18:05:00")
    assert "L1" in res["extension_reason"]


async def test_extensions_never_pass_forced_close(make_rfq, make_supplier, bid, client, clock):
    rfq = await make_rfq()  # close 18:00, forced 18:30
    a = await make_supplier("Alpha")
    forced = clock().replace(hour=18, minute=30)
    close = clock().replace(hour=18, minute=0)
    for i in range(10):  # keep sniping 30s before the (moving) close
        clock.set(close - timedelta(seconds=30))
        res = await bid(rfq["id"], a["id"], 1000 - i * 10)
        close = datetime.fromisoformat(res["current_close_at"])
        assert close <= forced

    detail = await _detail(client, rfq["id"])
    assert detail["current_close_at"].startswith("2030-01-15T18:30:00")
    assert detail["extension_count"] == 6  # 18:05 ... 18:30
    capped = [e for e in detail["activity"] if e["event_type"] == "AUCTION_EXTENDED"]
    assert len(capped) == 6

    clock.set(clock().replace(hour=18, minute=30))
    err = await bid(rfq["id"], a["id"], 1, expect=409)
    assert err["error"]["details"]["status"] == "FORCE_CLOSED"


async def test_partial_extension_is_capped(make_rfq, make_supplier, bid, client, clock):
    rfq = await make_rfq(bid_close_at=iso(clock().replace(hour=18, minute=28)))
    a = await make_supplier("Alpha")
    clock.set(clock().replace(hour=18, minute=25))
    res = await bid(rfq["id"], a["id"], 100)
    assert res["current_close_at"].startswith("2030-01-15T18:30:00")
    assert "capped" in res["extension_reason"]


async def test_activity_log_order_and_content(make_rfq, make_supplier, bid, client, clock):
    rfq = await make_rfq()
    a, b = await make_supplier("Alpha"), await make_supplier("Beta")
    clock.advance(minutes=1)
    await bid(rfq["id"], a["id"], 1000)
    clock.set(clock().replace(hour=17, minute=58))
    await bid(rfq["id"], b["id"], 900)

    log = (await client.get(f"{API}/rfqs/{rfq['id']}/activity")).json()
    assert [e["event_type"] for e in log] == ["AUCTION_EXTENDED", "BID_SUBMITTED", "BID_SUBMITTED", "RFQ_CREATED"]
    beta_bid = log[1]
    assert beta_bid["details"]["rank"] == 1
    assert beta_bid["details"]["ranking_before"] == [a["id"]]
    assert beta_bid["details"]["ranking_after"] == [b["id"], a["id"]]
    assert "Beta submitted a bid of 900.00" in beta_bid["message"]


async def test_concurrent_bids_are_serialised(make_rfq, make_supplier, client, clock):
    """Simultaneous bids in a wide window: each sees the previous close time, so all 8 extend (no lost updates)."""
    rfq = await make_rfq(trigger_window_minutes=60, forced_close_at=iso(clock().replace(hour=23)))
    suppliers = [await make_supplier(f"S{i}") for i in range(8)]
    clock.set(clock().replace(hour=17, minute=59))

    async def place(i, s):
        return await client.post(
            f"{API}/rfqs/{rfq['id']}/bids",
            json={
                "supplier_id": s["id"],
                "carrier_name": "X",
                "freight_charges": 1000 - i,
                "transit_time_days": 10,
                "quote_validity_date": "2030-02-01",
            },
        )

    responses = await asyncio.gather(*(place(i, s) for i, s in enumerate(suppliers)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]

    detail = await _detail(client, rfq["id"])
    assert detail["extension_count"] == 8
    assert detail["current_close_at"].startswith("2030-01-15T18:40:00")
    assert [r["bid"]["total_amount"] for r in detail["ranking"]] == sorted(1000 - i for i in range(8))


async def test_events_are_published_to_redis(make_rfq, make_supplier, bid, redis, clock):
    rfq = await make_rfq()
    a = await make_supplier("Alpha")
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"auctions:{rfq['id']}:events")
    await pubsub.get_message(timeout=1)  # subscribe confirmation

    clock.set(clock().replace(hour=17, minute=55))
    await bid(rfq["id"], a["id"], 500)

    received = []
    for _ in range(2):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2)
        assert msg is not None
        received.append(json.loads(msg["data"])["event_type"])
    assert received == ["BID_SUBMITTED", "AUCTION_EXTENDED"]
    await pubsub.aclose()
