import { useEffect, useState } from "react";
import { serverNow } from "./store";

/** Milliseconds until `targetIso` on the server clock, ticking once per second. */
export function useCountdown(targetIso: string | null, onElapsed?: () => void) {
  const target = targetIso ? Date.parse(targetIso) : null;
  const [remaining, setRemaining] = useState(() => (target ? target - serverNow() : 0));

  useEffect(() => {
    if (target == null) return;
    let fired = false;
    const tick = () => {
      const left = target - serverNow();
      setRemaining(left);
      if (left <= 0 && !fired) {
        fired = true;
        onElapsed?.();
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [target, onElapsed]);

  return remaining;
}

export function fmtDuration(ms: number) {
  if (ms <= 0) return "00:00";
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (d > 0) return `${d}d ${pad(h)}h ${pad(m)}m`;
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`;
}
