import { keepPreviousData, queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { http } from "./client";
import type {
  Bid,
  BidCreate,
  BidPlaced,
  Health,
  Page,
  RfqCreate,
  RfqDetail,
  RfqListParams,
  RfqSummary,
  Supplier,
  SupplierCreate,
} from "./types";
export const keys = {
  health: ["health"] as const,
  suppliers: ["suppliers"] as const,
  rfqs: ["rfqs"] as const,
  rfqList: (p: RfqListParams) => ["rfqs", p] as const,
  rfq: (id: number) => ["rfq", id] as const,
  rfqBids: (id: number) => ["rfq", id, "bids"] as const,
};

export const healthQuery = () =>
  queryOptions({ queryKey: keys.health, queryFn: ({ signal }) => http.get<Health>("/health", undefined, signal), staleTime: 60_000 });

export const suppliersQuery = () =>
  queryOptions({ queryKey: keys.suppliers, queryFn: ({ signal }) => http.get<Supplier[]>("/suppliers", undefined, signal), staleTime: 5 * 60_000 });

export const rfqListQuery = (p: RfqListParams) =>
  queryOptions({
    queryKey: keys.rfqList(p),
    queryFn: ({ signal }) => http.get<Page<RfqSummary>>("/rfqs", { ...p }, signal),
    placeholderData: keepPreviousData, // no flash of empty table while paging/filtering
    staleTime: 10_000,
  });

export const rfqDetailQuery = (id: number) =>
  queryOptions({ queryKey: keys.rfq(id), queryFn: ({ signal }) => http.get<RfqDetail>(`/rfqs/${id}`, undefined, signal), staleTime: 5_000 });

export const rfqBidsQuery = (id: number) =>
  queryOptions({ queryKey: keys.rfqBids(id), queryFn: ({ signal }) => http.get<Bid[]>(`/rfqs/${id}/bids`, undefined, signal), staleTime: 5_000 });

export function useCreateRfq() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RfqCreate) => http.post<RfqDetail>("/rfqs", body),
    onSuccess: (rfq) => {
      qc.setQueryData(keys.rfq(rfq.id), rfq); // detail page opens instantly
      qc.invalidateQueries({ queryKey: keys.rfqs });
    },
  });
}

export function usePlaceBid(rfqId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BidCreate) => http.post<BidPlaced>(`/rfqs/${rfqId}/bids`, body),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.rfq(rfqId) });
      qc.invalidateQueries({ queryKey: keys.rfqs });
    },
  });
}

export function useCreateSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SupplierCreate) => http.post<Supplier>("/suppliers", body),
    onSuccess: (s) => qc.setQueryData<Supplier[]>(keys.suppliers, (old = []) => [...old, s].sort((a, b) => a.name.localeCompare(b.name))),
  });
}
