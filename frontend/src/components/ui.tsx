import clsx from "clsx";
import type { ReactNode } from "react";
import type { AuctionStatus } from "@/api/types";
import { STATUS_COLOR, STATUS_LABEL } from "@/lib/format";
import { fmtDuration, useCountdown } from "@/lib/useCountdown";

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="truncate">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}

export function Section({ title, actions, children, className }: { title?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={clsx("card", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          {title && <h2>{title}</h2>}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Field({ label, error, hint, children, htmlFor }: { label: string; error?: string; hint?: string; children: ReactNode; htmlFor: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="mt-1 text-xs text-red-700">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  );
}


export function Notice({ tone = "info", children, action }: { tone?: "info" | "error" | "warning"; children: ReactNode; action?: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={clsx(
        "flex flex-wrap items-center justify-between gap-3 rounded-md border-l-4 px-4 py-3 text-sm",
        tone === "info" && "border-slate-300 bg-slate-100 text-slate-700",
        tone === "warning" && "border-amber-500 bg-amber-50 text-amber-900",
        tone === "error" && "border-red-600 bg-red-50 text-red-800",
      )}
    >
      <div>{children}</div>
      {action}
    </div>
  );
}

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty = "Nothing to show",
  rowClassName,
  onRowIntent,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  empty?: string;
  rowClassName?: (row: T) => string | undefined;
  
  onRowIntent?: (row: T) => void;
}) {
  if (rows.length === 0) return <p className="py-6 text-center text-sm text-slate-500">{empty}</p>;
  return (
    <div className="-mx-4 overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => (
              <th key={c.header} scope="col" className={clsx("whitespace-nowrap px-4 py-2 font-medium", c.align === "right" ? "text-right" : "text-left")}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={clsx("hover:bg-slate-50", rowClassName?.(row))}
              onMouseEnter={onRowIntent ? () => onRowIntent(row) : undefined}
              onFocus={onRowIntent ? () => onRowIntent(row) : undefined}
            >
              {columns.map((c) => (
                <td key={c.header} className={clsx("px-4 py-2.5 align-top", c.align === "right" && "num text-right", c.className)}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <nav className="mt-4 flex items-center justify-between text-sm text-slate-600" aria-label="Pagination">
      <span className="num">
        {from}–{to} of {total}
      </span>
      <div className="flex gap-2">
        <button className="btn-secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          Previous
        </button>
        <button className="btn-secondary" disabled={to >= total} onClick={() => onChange(offset + limit)}>
          Next
        </button>
      </div>
    </nav>
  );
}

export function StatusText({ status, className }: { status: AuctionStatus; className?: string }) {
  return <span className={clsx("font-medium", STATUS_COLOR[status], className)}>{STATUS_LABEL[status]}</span>;
}

export function Countdown({ to, onElapsed, urgentBelowMs, className }: { to: string; onElapsed?: () => void; urgentBelowMs?: number; className?: string }) {
  const left = useCountdown(to, onElapsed);
  const urgent = urgentBelowMs != null && left > 0 && left <= urgentBelowMs;
  return <span className={clsx("num", urgent ? "font-semibold text-amber-700" : "text-slate-700", className)}>{fmtDuration(left)}</span>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-slate-500" role="status">
      <span className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-accent" />
      {label}
    </div>
  );
}
