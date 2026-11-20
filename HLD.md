# High-Level Design: RFQ British Auction

_generated using online mermaid editor_

## 1. Overview

A simplified RFQ (Request for Quotation) system where suppliers compete in a **British
(reverse) auction**: they submit quotes openly and keep lowering them.

- Bidding activity near the close **extends** the auction automatically.
- The auction can never run past a **forced close time**.
---
## 2. Architecture

```mermaid
flowchart LR
    U["Browser<br/>(Buyer / Supplier)"]

    subgraph Docker["Docker Compose"]
        direction LR
        W["web<br/>nginx + React SPA<br/>:3000"]
        A["api<br/>FastAPI (Python 3.12)<br/>:8000"]
        C["Closer job<br/>(background task in api)"]
        P[("PostgreSQL 16<br/>source of truth")]
        R[("Redis 7<br/>pub/sub + lock")]
    end

    U -- "HTTPS: pages, /api/v1 REST" --> W
    U -. "SSE: live events" .-> W
    W -- "proxy /api" --> A
    A -- "SQL (row lock on bid)" --> P
    A -- "PUBLISH events" --> R
    R -- "SUBSCRIBE (SSE streams)" --> A
    C -- "close due auctions" --> P
    C -- "SET NX lock + PUBLISH" --> R
```

## 3. Backend layers

```mermaid
flowchart TB
    R["Routes<br/>api/routes/*.py"] --> S["Schemas<br/>Pydantic validation"]
    R --> SV["Services<br/>rfq_service · bid_service · closer · events"]
    SV --> RU["auction_rules.py<br/>pure functions: status, ranking, extension"]
    SV --> M["Models<br/>SQLAlchemy"]
    M --> DB[("PostgreSQL")]
    SV --> RD[("Redis")]
```