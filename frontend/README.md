# RFQ British Auction – Frontend

React 19 + TypeScript + Vite.

## Run

```bash
docker compose up -d --build        # from the repo root → http://localhost:3000
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server; `/api` is proxied to `http://localhost:8000` (override with `API_URL`) |
| `npm run build` | Type-check + production build into `dist/` |
| `npm run typecheck` | TypeScript only |
| `npm run analyze` | Build + bundle treemap at `dist/stats.html` |

## Structure

```
src/
  main.tsx
  index.css
  api/
  lib/
  components/
    Layout.tsx
    ui.tsx
  pages/
    AuctionListPage
    CreateRfqPage
    AuctionDetailPage
      auction-detail/ BidForm (lazy), ActivityLog
    SuppliersPage
```
