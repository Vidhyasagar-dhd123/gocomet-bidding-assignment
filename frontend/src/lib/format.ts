import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import type { AuctionStatus, ExtensionTrigger } from "@/api/types";
import { serverNow } from "./store";

dayjs.extend(relativeTime);

const money = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtMoney = (v: number | null | undefined) => (v == null ? "—" : money.format(v));
export const fmtDateTime = (iso: string | null | undefined) => (iso ? dayjs(iso).format("DD MMM YYYY, HH:mm:ss") : "—");
export const fmtTime = (iso: string) => dayjs(iso).format("HH:mm:ss");
export const fmtDate = (iso: string) => dayjs(iso).format("DD MMM YYYY");
/** Relative to the server clock, so "a minute ago" is right even if the local clock drifts. */
export const fromNow = (iso: string) => dayjs(iso).from(serverNow());

/** `datetime-local` value (local, no tz) → ISO with timezone, as the API requires. */
export const localToIso = (v: string) => new Date(v).toISOString();
/** Date → `datetime-local` input value. */
export const toLocalInput = (d: Date) => dayjs(d).format("YYYY-MM-DDTHH:mm");

export const STATUS_LABEL: Record<AuctionStatus, string> = {
  SCHEDULED: "Scheduled",
  ACTIVE: "Active",
  CLOSED: "Closed",
  FORCE_CLOSED: "Force closed",
};

/** Status is distinguished by text colour only (no badges). */
export const STATUS_COLOR: Record<AuctionStatus, string> = {
  SCHEDULED: "text-slate-500",
  ACTIVE: "text-green-700",
  CLOSED: "text-slate-700",
  FORCE_CLOSED: "text-red-700",
};

export const TRIGGER_LABEL: Record<ExtensionTrigger, string> = {
  BID_RECEIVED: "Bid received",
  ANY_RANK_CHANGE: "Any rank change",
  L1_RANK_CHANGE: "Lowest bidder (L1) change",
};

export const TRIGGER_HELP: Record<ExtensionTrigger, string> = {
  BID_RECEIVED: "Any new bid in the last X minutes extends the auction.",
  ANY_RANK_CHANGE: "Extends only when a supplier's position changes in the last X minutes.",
  L1_RANK_CHANGE: "Extends only when a different supplier becomes the lowest bidder.",
};
