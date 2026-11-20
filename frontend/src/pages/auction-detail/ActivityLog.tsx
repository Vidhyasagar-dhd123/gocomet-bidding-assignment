import clsx from "clsx";
import type { AuctionEvent, AuctionEventType } from "@/api/types";
import { fmtDateTime, fmtTime } from "@/lib/format";
const TONE: Record<AuctionEventType, string> = {
  RFQ_CREATED: "border-slate-300",
  BID_SUBMITTED: "border-blue-400",
  AUCTION_EXTENDED: "border-amber-500 bg-amber-50/60",
  AUCTION_CLOSED: "border-green-600",
  AUCTION_FORCE_CLOSED: "border-red-600",
};

const TITLE: Record<AuctionEventType, string> = {
  RFQ_CREATED: "RFQ created",
  BID_SUBMITTED: "Bid submitted",
  AUCTION_EXTENDED: "Time extended",
  AUCTION_CLOSED: "Auction closed",
  AUCTION_FORCE_CLOSED: "Auction force closed",
};

export default function ActivityLog({ events }: { events: AuctionEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-slate-500">No activity yet.</p>;
  return (
    <ol className="max-h-[32rem] space-y-2 overflow-y-auto pr-1 [content-visibility:auto]">
      {events.map((e) => {
        const d = e.details as Record<string, string | number | boolean | null>;
        return (
          <li key={e.id} className={clsx("border-l-4 py-1.5 pl-3", TONE[e.event_type])}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
              <span className="font-medium text-slate-900">{TITLE[e.event_type]}</span>
              <time className="num text-xs text-slate-500" dateTime={e.created_at} title={fmtDateTime(e.created_at)}>
                {fmtTime(e.created_at)}
              </time>
            </div>
            {e.event_type === "AUCTION_EXTENDED" ? (
              <p className="text-sm text-slate-700">
                <span className="num">
                  {fmtTime(String(d.previous_close_at))} → {fmtTime(String(d.new_close_at))}
                </span>{" "}
                (+{Number(d.applied_minutes)} min). <span className="text-amber-800">Reason: {String(d.reason)}</span>
              </p>
            ) : (
              <p className="text-sm text-slate-600">{e.message}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
