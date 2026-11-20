# Database Schema: RFQ British Auction
`Just added ER diagram due to time constraint`  
PostgreSQL database, managed by Alembic (`backend/alembic/versions/0001_initial_schema.py`).
There are 4 tables. All timestamps are `timestamptz`, and money is `NUMERIC(14,2)`.

## ER diagram

```mermaid
erDiagram
    SUPPLIERS ||--o{ BIDS : "places"
    RFQS ||--o{ BIDS : "receives"
    RFQS ||--o{ AUCTION_EVENTS : "logs"
    SUPPLIERS |o--o{ AUCTION_EVENTS : "actor of"
    BIDS |o--o{ AUCTION_EVENTS : "referenced by"

    SUPPLIERS {
        int id PK
        varchar name UK
        varchar contact_email
        timestamptz created_at
    }

    RFQS {
        int id PK
        varchar reference_id UK
        varchar name
        text description
        date pickup_date
        timestamptz bid_start_at
        timestamptz bid_close_at "original close, never changes"
        timestamptz current_close_at "live close, moves with extensions"
        timestamptz forced_close_at "hard stop"
        int trigger_window_minutes "X"
        int extension_minutes "Y"
        varchar extension_trigger "BID_RECEIVED | ANY_RANK_CHANGE | L1_RANK_CHANGE"
        int extension_count
        timestamptz closed_at "set by closer job"
        varchar final_status "CLOSED | FORCE_CLOSED"
        timestamptz created_at
        timestamptz updated_at
    }

    BIDS {
        int id PK
        int rfq_id FK
        int supplier_id FK
        varchar carrier_name
        numeric freight_charges
        numeric origin_charges
        numeric destination_charges
        numeric total_amount "sum of the three charges"
        int transit_time_days
        date quote_validity_date
        text remarks
        timestamptz created_at
    }

    AUCTION_EVENTS {
        bigint id PK
        int rfq_id FK
        varchar event_type "RFQ_CREATED | BID_SUBMITTED | AUCTION_EXTENDED | AUCTION_CLOSED | AUCTION_FORCE_CLOSED"
        int supplier_id FK "nullable"
        int bid_id FK "nullable"
        text message
        jsonb details "reason, old/new close, ranks..."
        timestamptz created_at
    }
```
