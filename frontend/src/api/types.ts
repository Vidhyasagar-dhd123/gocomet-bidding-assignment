export type AuctionStatus = "SCHEDULED" | "ACTIVE" | "CLOSED" | "FORCE_CLOSED";
export type ExtensionTrigger = "BID_RECEIVED" | "ANY_RANK_CHANGE" | "L1_RANK_CHANGE";
export type AuctionEventType =
  | "RFQ_CREATED"
  | "BID_SUBMITTED"
  | "AUCTION_EXTENDED"
  | "AUCTION_CLOSED"
  | "AUCTION_FORCE_CLOSED";

export interface AuctionConfig {
  trigger_window_minutes: number;
  extension_minutes: number;
  extension_trigger: ExtensionTrigger;
}

export interface RfqCreate extends AuctionConfig {
  reference_id?: string | null;
  name: string;
  description?: string | null;
  pickup_date: string;
  bid_start_at: string;
  bid_close_at: string;
  forced_close_at: string;
}

export interface BidCreate {
  supplier_id: number;
  carrier_name: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  transit_time_days: number;
  quote_validity_date: string;
  remarks?: string | null;
}

export interface SupplierCreate {
  name: string;
  contact_email?: string | null;
}

export interface Supplier {
  id: number;
  name: string;
  contact_email: string | null;
  created_at: string;
}

export interface Bid {
  id: number;
  rfq_id: number;
  supplier_id: number;
  supplier_name: string;
  carrier_name: string;
  freight_charges: number;
  origin_charges: number;
  destination_charges: number;
  total_amount: number;
  transit_time_days: number;
  quote_validity_date: string;
  remarks: string | null;
  created_at: string;
}

export interface RankedBid {
  rank: number;
  rank_label: string;
  bid_count: number;
  bid: Bid;
}

export interface RfqSummary {
  id: number;
  reference_id: string;
  name: string;
  status: AuctionStatus;
  pickup_date: string;
  bid_start_at: string;
  bid_close_at: string;
  current_close_at: string;
  forced_close_at: string;
  extension_count: number;
  lowest_bid: number | null;
  bid_count: number;
  supplier_count: number;
}

export interface AuctionEvent {
  id: number;
  event_type: AuctionEventType;
  supplier_id: number | null;
  bid_id: number | null;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface RfqDetail extends RfqSummary {
  description: string | null;
  config: AuctionConfig;
  closed_at: string | null;
  created_at: string;
  server_time: string;
  ranking: RankedBid[];
  activity: AuctionEvent[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface BidPlaced {
  bid: Bid;
  rank: number;
  rank_label: string;
  auction_extended: boolean;
  extension_reason: string | null;
  current_close_at: string;
  forced_close_at: string;
}

export interface Health {
  status: "ok" | "degraded";
  database: boolean;
  redis: boolean;
  server_time: string;
}

export interface StreamEvent extends AuctionEvent {
  rfq_id: number;
}

export interface RfqListParams {
  status?: AuctionStatus;
  search?: string;
  limit: number;
  offset: number;
}
