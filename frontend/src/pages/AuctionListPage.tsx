import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { useDebounce } from "use-debounce";
import { keys, rfqDetailQuery, rfqListQuery } from "@/api/queries";
import type { AuctionStatus, RfqSummary } from "@/api/types";
import { Countdown, DataTable, Notice, PageHeader, Pagination, Section, Spinner, StatusText, type Column } from "@/components/ui";
import { fmtDateTime, fmtMoney, STATUS_LABEL } from "@/lib/format";
import { useAuctionStream } from "@/lib/useAuctionStream";

const LIMIT = 20;
const STATUSES = Object.keys(STATUS_LABEL) as AuctionStatus[];

export function Component() {
  
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") as AuctionStatus | null) ?? undefined;
  const q = params.get("q") ?? "";
  const offset = Number(params.get("offset") ?? 0) || 0;
  const [search] = useDebounce(q.trim(), 300);

  const qc = useQueryClient();
  const list = useQuery(rfqListQuery({ status, search: search || undefined, limit: LIMIT, offset }));

  
  useAuctionStream("/events/stream", [keys.rfqs], undefined, 1000);

  const update = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v ? next.set(k, v) : next.delete(k));
    setParams(next, { replace: true });
  };

  const refetchList = () => qc.invalidateQueries({ queryKey: keys.rfqs });

  const columns: Column<RfqSummary>[] = [
    {
      header: "RFQ",
      cell: (r) => (
        <Link to={`/auctions/${r.id}`} className="block min-w-48">
          <span className="font-medium text-slate-900 hover:text-accent">{r.name}</span>
          <span className="block text-xs text-slate-500">{r.reference_id}</span>
        </Link>
      ),
    },
    { header: "Status", cell: (r) => <StatusText status={r.status} /> },
    {
      header: "Lowest bid",
      align: "right",
      cell: (r) => (
        <>
          <span className={r.lowest_bid == null ? "text-slate-400" : "font-semibold text-green-700"}>{fmtMoney(r.lowest_bid)}</span>
          <span className="block text-xs text-slate-500">
            {r.bid_count} bids · {r.supplier_count} suppliers
          </span>
        </>
      ),
    },
    {
      header: "Current close",
      cell: (r) => (
        <div className="whitespace-nowrap">
          <span className={r.extension_count > 0 ? "text-amber-700" : undefined}>{fmtDateTime(r.current_close_at)}</span>
          <span className="block text-xs text-slate-500">
            {r.status === "ACTIVE" ? (
              <>
                ends in <Countdown to={r.current_close_at} onElapsed={refetchList} urgentBelowMs={10 * 60_000} />
              </>
            ) : r.status === "SCHEDULED" ? (
              <>
                starts in <Countdown to={r.bid_start_at} onElapsed={refetchList} />
              </>
            ) : null}
            {r.extension_count > 0 && ` · extended ${r.extension_count}×`}
          </span>
        </div>
      ),
    },
    { header: "Forced close", cell: (r) => <span className="whitespace-nowrap text-slate-600">{fmtDateTime(r.forced_close_at)}</span> },
  ];

  return (
    <>
      <PageHeader
        title="British auctions"
        subtitle="All RFQs with live lowest bid and close times."
        actions={
          <Link to="/auctions/new" className="btn-primary hover:text-white">
            New RFQ
          </Link>
        }
      />
      <Section>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="search"
            className="input sm:max-w-xs"
            placeholder="Search name or reference"
            aria-label="Search auctions"
            value={q}
            maxLength={100}
            onChange={(e) => update({ q: e.target.value, offset: undefined })}
          />
          <select
            className="input sm:max-w-48"
            aria-label="Filter by status"
            value={status ?? ""}
            onChange={(e) => update({ status: e.target.value || undefined, offset: undefined })}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
        </div>

        {list.isPending ? (
          <Spinner />
        ) : list.isError ? (
          <Notice tone="error" action={<button className="btn-secondary" onClick={() => list.refetch()}>Retry</button>}>
            {list.error.message}
          </Notice>
        ) : (
          <div className={list.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
            <DataTable
              columns={columns}
              rows={list.data.items}
              rowKey={(r) => r.id}
              empty={search || status ? "No auctions match these filters." : "No auctions yet. Create the first RFQ."}
              
              onRowIntent={(r) => void qc.prefetchQuery(rfqDetailQuery(r.id))}
            />
            <Pagination total={list.data.total} limit={LIMIT} offset={offset} onChange={(o) => update({ offset: o ? String(o) : undefined })} />
          </div>
        )}
      </Section>
    </>
  );
}
