import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { healthQuery, keys, rfqBidsQuery, rfqDetailQuery } from "@/api/queries";
import type { Bid, RankedBid, RfqDetail } from "@/api/types";
import { Countdown, DataTable, Notice, PageHeader, Section, Spinner, StatusText, type Column } from "@/components/ui";
import { fmtDate, fmtDateTime, fmtMoney, fmtTime, fromNow, TRIGGER_LABEL } from "@/lib/format";
import { serverNow, useAppStore } from "@/lib/store";
import { useAuctionStream } from "@/lib/useAuctionStream";
import ActivityLog from "./auction-detail/ActivityLog";


const BidForm = lazy(() => import("./auction-detail/BidForm"));

export function Component() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const redisOk = useQuery(healthQuery()).data?.redis ?? true;
  const syncClock = useAppStore((s) => s.syncClock);

  const detail = useQuery({
    ...rfqDetailQuery(id),
    enabled: Number.isInteger(id) && id > 0,
    
    refetchInterval: (q) => (!redisOk && q.state.data?.status === "ACTIVE" ? 5000 : false),
  });

  useEffect(() => {
    if (detail.data) syncClock(detail.data.server_time);
  }, [detail.data, syncClock]);

  useAuctionStream(redisOk && id > 0 ? `/rfqs/${id}/stream` : null, [keys.rfq(id), keys.rfqBids(id)], (e) => {
    if (e.event_type === "AUCTION_EXTENDED") toast.warning("Auction extended", { description: String(e.details.reason ?? e.message) });
    if (e.event_type === "AUCTION_CLOSED" || e.event_type === "AUCTION_FORCE_CLOSED") toast.info(e.message);
  });

  if (detail.isPending) return <Spinner />;
  if (detail.isError)
    return detail.error instanceof ApiError && detail.error.status === 404 ? (
      <Notice action={<Link to="/auctions">Back to auctions</Link>}>Auction not found.</Notice>
    ) : (
      <Notice tone="error" action={<button className="btn-secondary" onClick={() => detail.refetch()}>Retry</button>}>
        {detail.error.message}
      </Notice>
    );

  const rfq = detail.data;
  const refresh = () => qc.invalidateQueries({ queryKey: keys.rfq(id) });

  return (
    <>
      <PageHeader
        title={rfq.name}
        subtitle={
          <>
            {rfq.reference_id} · <StatusText status={rfq.status} />
          </>
        }
        actions={<Link to="/auctions" className="btn-secondary">All auctions</Link>}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
          <Timing rfq={rfq} onElapsed={refresh} />
          <BidsSection rfq={rfq} />
        </div>
        <div className="flex flex-col gap-6">
          <Section title="Submit quote">
            {rfq.status === "ACTIVE" ? (
              <Suspense fallback={<Spinner />}>
                <BidForm rfqId={rfq.id} ranking={rfq.ranking} pickupDate={rfq.pickup_date} />
              </Suspense>
            ) : rfq.status === "SCHEDULED" ? (
              <Notice>
                Bidding opens in <Countdown to={rfq.bid_start_at} onElapsed={refresh} />.
              </Notice>
            ) : (
              <Notice tone={rfq.status === "FORCE_CLOSED" ? "error" : "info"}>
                Auction {rfq.status === "FORCE_CLOSED" ? "force closed" : "closed"} at {fmtDateTime(rfq.current_close_at)}.
                {rfq.ranking[0] && ` Winner: ${rfq.ranking[0].bid.supplier_name} at ${fmtMoney(rfq.ranking[0].bid.total_amount)}.`}
              </Notice>
            )}
          </Section>
          <Section title="Activity">
            <ActivityLog events={rfq.activity} />
          </Section>
        </div>
      </div>
    </>
  );
}

function Timing({ rfq, onElapsed }: { rfq: RfqDetail; onElapsed: () => void }) {
  const windowMs = rfq.config.trigger_window_minutes * 60_000;
  const inWindow = rfq.status === "ACTIVE" && Date.parse(rfq.current_close_at) - serverNow() <= windowMs;
  const extended = rfq.current_close_at !== rfq.bid_close_at;

  return (
    <Section title="Auction">
      <div className="grid gap-x-6 gap-y-4 sm:grid-cols-[minmax(0,14rem)_1fr]">
        <div>
          <p className="text-sm text-slate-500">{rfq.status === "SCHEDULED" ? "Starts in" : rfq.status === "ACTIVE" ? "Closes in" : "Closed"}</p>
          <p className="text-3xl font-semibold tracking-tight">
            {rfq.status === "ACTIVE" ? (
              <Countdown to={rfq.current_close_at} onElapsed={onElapsed} urgentBelowMs={windowMs} />
            ) : rfq.status === "SCHEDULED" ? (
              <Countdown to={rfq.bid_start_at} onElapsed={onElapsed} />
            ) : (
              <span className="text-slate-700">{fmtTime(rfq.closed_at ?? rfq.current_close_at)}</span>
            )}
          </p>
          {inWindow && <p className="mt-1 text-sm text-amber-700">Extension window open</p>}
          <p className="mt-3 text-sm text-slate-500">Lowest bid</p>
          <p className={clsx("num text-xl font-semibold", rfq.lowest_bid == null ? "text-slate-400" : "text-green-700")}>{fmtMoney(rfq.lowest_bid)}</p>
          <p className="text-xs text-slate-500">
            {rfq.bid_count} bids · {rfq.supplier_count} suppliers
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <Item label="Bid start">{fmtDateTime(rfq.bid_start_at)}</Item>
          <Item label="Original close">{fmtDateTime(rfq.bid_close_at)}</Item>
          <Item label="Current close">
            <span className={clsx(extended && "font-medium text-amber-700")}>{fmtDateTime(rfq.current_close_at)}</span>
          </Item>
          <Item label="Forced close">
            <span className="text-red-700">{fmtDateTime(rfq.forced_close_at)}</span>
          </Item>
          <Item label="Trigger window (X)">{rfq.config.trigger_window_minutes} min</Item>
          <Item label="Extension (Y)">{rfq.config.extension_minutes} min</Item>
          <Item label="Extension trigger">{TRIGGER_LABEL[rfq.config.extension_trigger]}</Item>
          <Item label="Extensions so far">{rfq.extension_count}</Item>
          <Item label="Pickup / service date">{fmtDate(rfq.pickup_date)}</Item>
          {rfq.description && <Item label="Description">{rfq.description}</Item>}
        </dl>
      </div>
    </Section>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="num break-words text-slate-900">{children}</dd>
    </div>
  );
}

const quoteColumns: Column<Bid>[] = [
  { header: "Total", align: "right", cell: (b) => <strong className="text-slate-900">{fmtMoney(b.total_amount)}</strong> },
  { header: "Carrier", cell: (b) => b.carrier_name },
  { header: "Freight", align: "right", cell: (b) => fmtMoney(b.freight_charges) },
  { header: "Origin", align: "right", cell: (b) => fmtMoney(b.origin_charges) },
  { header: "Destination", align: "right", cell: (b) => fmtMoney(b.destination_charges) },
  { header: "Transit", align: "right", cell: (b) => `${b.transit_time_days} d` },
  { header: "Valid until", cell: (b) => <span className="whitespace-nowrap">{fmtDate(b.quote_validity_date)}</span> },
];

function BidsSection({ rfq }: { rfq: RfqDetail }) {
  const [view, setView] = useState<"ranking" | "all">("ranking");
  const acting = useAppStore((s) => s.actingSupplierId);
  
  const history = useQuery({ ...rfqBidsQuery(rfq.id), enabled: view === "all" });

  const rankingColumns: Column<RankedBid>[] = [
    {
      header: "Rank",
      cell: (r) => <span className={clsx("font-semibold", r.rank === 1 ? "text-green-700" : "text-slate-600")}>{r.rank_label}</span>,
    },
    {
      header: "Supplier",
      cell: (r) => (
        <div className="min-w-36">
          <span className="font-medium text-slate-900">{r.bid.supplier_name}</span>
          {r.bid.supplier_id === acting && <span className="text-accent"> (you)</span>}
          <span className="block text-xs text-slate-500">
            {r.bid_count} bid{r.bid_count > 1 && "s"} · {fromNow(r.bid.created_at)}
          </span>
          {r.bid.remarks && <span className="block text-xs text-slate-500">{r.bid.remarks}</span>}
        </div>
      ),
    },
    ...quoteColumns.map((c) => ({ ...c, cell: (r: RankedBid) => c.cell(r.bid) })),
  ];

  const historyColumns: Column<Bid>[] = [
    { header: "Supplier", cell: (b) => <span className="font-medium text-slate-900">{b.supplier_name}</span> },
    ...quoteColumns,
    { header: "Placed", cell: (b) => <span className="num whitespace-nowrap text-slate-500">{fmtDateTime(b.created_at)}</span> },
  ];

  const tab = (key: typeof view, label: string) => (
    <button
      type="button"
      aria-pressed={view === key}
      onClick={() => setView(key)}
      className={clsx("rounded-md px-3 py-1 text-sm font-medium", view === key ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900")}
    >
      {label}
    </button>
  );

  return (
    <Section title="Bids" actions={<div className="flex gap-1">{tab("ranking", "Ranking")}{tab("all", "All bids")}</div>}>
      {view === "ranking" ? (
        <DataTable
          columns={rankingColumns}
          rows={rfq.ranking}
          rowKey={(r) => r.bid.supplier_id}
          empty="No bids yet."
          rowClassName={(r) => (r.bid.supplier_id === acting ? "bg-blue-50/60" : undefined)}
        />
      ) : history.isPending ? (
        <Spinner />
      ) : history.isError ? (
        <Notice tone="error">{history.error.message}</Notice>
      ) : (
        <DataTable columns={historyColumns} rows={history.data} rowKey={(b) => b.id} empty="No bids yet." />
      )}
    </Section>
  );
}
