from datetime import timedelta

from tests.conftest import API, iso


async def test_create_rfq_and_details(make_rfq, client):
    rfq = await make_rfq(reference_id="RFQ-001")
    assert rfq["reference_id"] == "RFQ-001"
    assert rfq["status"] == "ACTIVE"
    assert rfq["current_close_at"] == rfq["bid_close_at"]
    assert rfq["config"] == {"trigger_window_minutes": 10, "extension_minutes": 5, "extension_trigger": "BID_RECEIVED"}
    assert rfq["lowest_bid"] is None
    assert [e["event_type"] for e in rfq["activity"]] == ["RFQ_CREATED"]

    detail = (await client.get(f"{API}/rfqs/{rfq['id']}")).json()
    assert detail["id"] == rfq["id"]


async def test_reference_id_is_generated_and_unique(make_rfq, client, clock):
    rfq = await make_rfq()
    assert rfq["reference_id"].startswith("RFQ-")

    await make_rfq(reference_id="DUP-1")
    now = clock()
    resp = await client.post(
        f"{API}/rfqs",
        json={
            "reference_id": "DUP-1",
            "name": "Another",
            "pickup_date": (now + timedelta(days=3)).date().isoformat(),
            "bid_start_at": iso(now),
            "bid_close_at": iso(now + timedelta(hours=1)),
            "forced_close_at": iso(now + timedelta(hours=2)),
            "trigger_window_minutes": 5,
            "extension_minutes": 5,
        },
    )
    assert resp.status_code == 409


def _payload(clock, **overrides):
    now = clock()
    data = {
        "name": "Invalid RFQ",
        "pickup_date": (now + timedelta(days=3)).date().isoformat(),
        "bid_start_at": iso(now),
        "bid_close_at": iso(now + timedelta(hours=1)),
        "forced_close_at": iso(now + timedelta(hours=2)),
        "trigger_window_minutes": 10,
        "extension_minutes": 5,
    }
    data.update(overrides)
    return data


async def test_forced_close_must_be_after_bid_close(client, clock):
    now = clock()
    for forced in (now + timedelta(hours=1), now + timedelta(minutes=30)):
        resp = await client.post(f"{API}/rfqs", json=_payload(clock, forced_close_at=iso(forced)))
        assert resp.status_code == 422
        assert "Forced bid close time must be later" in resp.text


async def test_close_must_be_after_start(client, clock):
    now = clock()
    resp = await client.post(f"{API}/rfqs", json=_payload(clock, bid_close_at=iso(now - timedelta(minutes=1))))
    assert resp.status_code == 422


async def test_close_must_be_in_future(client, clock):
    now = clock()
    resp = await client.post(
        f"{API}/rfqs",
        json=_payload(
            clock,
            bid_start_at=iso(now - timedelta(hours=2)),
            bid_close_at=iso(now - timedelta(hours=1)),
            forced_close_at=iso(now + timedelta(hours=1)),
        ),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["message"] == "Bid close time must be in the future"


async def test_timezone_required_and_config_bounds(client, clock):
    resp = await client.post(f"{API}/rfqs", json=_payload(clock, bid_start_at="2030-01-15T17:00:00"))
    assert resp.status_code == 422
    resp = await client.post(f"{API}/rfqs", json=_payload(clock, trigger_window_minutes=0))
    assert resp.status_code == 422
    resp = await client.post(f"{API}/rfqs", json=_payload(clock, extension_trigger="NOPE"))
    assert resp.status_code == 422


async def test_listing_shows_lowest_bid_and_status(make_rfq, make_supplier, bid, client, clock):
    a = await make_rfq(name="Active lane")
    upcoming = await make_rfq(
        name="Upcoming lane",
        bid_start_at=iso(clock() + timedelta(minutes=30)),
    )
    s1, s2 = await make_supplier("Alpha"), await make_supplier("Beta")
    await bid(a["id"], s1["id"], 1000)
    await bid(a["id"], s2["id"], 900)

    page = (await client.get(f"{API}/rfqs")).json()
    assert page["total"] == 2
    rows = {r["id"]: r for r in page["items"]}
    assert rows[a["id"]]["lowest_bid"] == 900
    assert rows[a["id"]]["bid_count"] == 2
    assert rows[a["id"]]["supplier_count"] == 2
    assert rows[a["id"]]["status"] == "ACTIVE"
    assert rows[upcoming["id"]]["status"] == "SCHEDULED"
    for key in ("reference_id", "current_close_at", "forced_close_at"):
        assert key in rows[a["id"]]

    active = (await client.get(f"{API}/rfqs", params={"status": "ACTIVE"})).json()
    assert [r["id"] for r in active["items"]] == [a["id"]]

    found = (await client.get(f"{API}/rfqs", params={"search": "upcoming"})).json()
    assert [r["id"] for r in found["items"]] == [upcoming["id"]]


async def test_listing_closed_vs_force_closed(make_rfq, make_supplier, bid, client, clock):
    normal = await make_rfq(name="Normal")
    forced = await make_rfq(name="Forced", bid_close_at=iso(clock().replace(hour=18, minute=28)))
    s = await make_supplier("Alpha")
    clock.set(clock().replace(hour=18, minute=27))
    await bid(forced["id"], s["id"], 500)  # extends 18:28 -> capped at 18:30

    clock.set(clock().replace(hour=18, minute=31))
    rows = {r["id"]: r for r in (await client.get(f"{API}/rfqs")).json()["items"]}
    assert rows[normal["id"]]["status"] == "CLOSED"
    assert rows[forced["id"]]["status"] == "FORCE_CLOSED"

    fc = (await client.get(f"{API}/rfqs", params={"status": "FORCE_CLOSED"})).json()["items"]
    assert [r["id"] for r in fc] == [forced["id"]]


async def test_unknown_rfq_404(client):
    assert (await client.get(f"{API}/rfqs/999")).status_code == 404
    assert (await client.get(f"{API}/rfqs/999/bids")).status_code == 404
    assert (await client.get(f"{API}/rfqs/999/activity")).status_code == 404


async def test_supplier_crud(client, make_supplier):
    await make_supplier("Alpha")
    dup = await client.post(f"{API}/suppliers", json={"name": "Alpha"})
    assert dup.status_code == 409
    assert [s["name"] for s in (await client.get(f"{API}/suppliers")).json()] == ["Alpha"]


async def test_health(client):
    body = (await client.get(f"{API}/health")).json()
    assert body["database"] is True and body["redis"] is True
