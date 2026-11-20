import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useThrottledCallback } from "use-debounce";
import { streamUrl } from "@/api/client";
import type { StreamEvent } from "@/api/types";

const EVENT_TYPES = ["RFQ_CREATED", "BID_SUBMITTED", "AUCTION_EXTENDED", "AUCTION_CLOSED", "AUCTION_FORCE_CLOSED"] as const;

/**
 * Subscribes to a server-sent-events stream and treats every event as a signal to
 * refetch (Postgres is the source of truth). Invalidations are throttled so a burst
 * of bids causes at most one refetch per `throttleMs`.
 */
export function useAuctionStream(
  path: string | null,
  queryKeys: readonly (readonly unknown[])[],
  onEvent?: (e: StreamEvent) => void,
  throttleMs = 500,
) {
  const qc = useQueryClient();
  const keysRef = useRef(queryKeys);
  const cbRef = useRef(onEvent);
  keysRef.current = queryKeys;
  cbRef.current = onEvent;

  const refresh = useThrottledCallback(
    () => keysRef.current.forEach((queryKey) => qc.invalidateQueries({ queryKey })),
    throttleMs,
    { leading: true, trailing: true },
  );

  useEffect(() => {
    if (!path) return;
    const es = new EventSource(streamUrl(path));
    const handler = (m: MessageEvent) => {
      cbRef.current?.(JSON.parse(m.data) as StreamEvent);
      refresh();
    };
    // Events are *named* (`event: BID_SUBMITTED`), so onmessage would never fire.
    EVENT_TYPES.forEach((t) => es.addEventListener(t, handler));
    es.onopen = () => refresh(); // catch up on anything missed while reconnecting
    return () => es.close();
  }, [path, refresh]);
}
