# RFQ Reverse Auction Backend

A backend service built with **FastAPI**, **PostgreSQL**, and **Redis** for running reverse auctions where suppliers compete by placing the lowest bid.

## Quick Start

1. **Start the app:**
   ```bash
   docker compose up -d --build
   ```
2. **Explore the API:** Open http://localhost:8000/docs in your browser to test endpoints.
3. **Run tests:**
   ```bash
   docker compose --profile test run --rm api-tests
   ```

## How It Works
- **Lowest Bid Wins:** Suppliers are ranked from lowest to highest (`L1`, `L2`, etc.). Each new bid from a supplier must be lower than their previous bid.
- **Auto-Extensions:** If a qualifying bid arrives right before the deadline, the auction automatically extends by a few minutes (up to a hard forced-close limit).
- **Live Updates:** Real-time auction events are streamed using Redis and Server-Sent Events (SSE).

## Key Endpoints
- `POST /api/v1/suppliers` — Add a new supplier
- `POST /api/v1/rfqs` — Create a new auction (RFQ)
- `POST /api/v1/rfqs/{id}/bids` — Place a bid
- `GET /api/v1/rfqs/{id}` — View auction status, rankings, and activity log
