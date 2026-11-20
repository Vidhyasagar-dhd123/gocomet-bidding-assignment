import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { Suspense, useEffect } from "react";
import { NavLink, Outlet, useNavigation } from "react-router-dom";
import { Toaster } from "sonner";
import { healthQuery, suppliersQuery } from "@/api/queries";
import { useAppStore } from "@/lib/store";
import { Notice, Spinner } from "./ui";

const NAV = [
  { to: "/auctions", label: "Auctions", end: true },
  { to: "/auctions/new", label: "New RFQ", end: true },
  { to: "/suppliers", label: "Suppliers", end: true },
];

export default function Layout() {
  const navigation = useNavigation();
  const health = useQuery(healthQuery());
  const syncClock = useAppStore((s) => s.syncClock);

  useEffect(() => {
    if (health.data) syncClock(health.data.server_time);
  }, [health.data, syncClock]);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <NavLink to="/auctions" className="text-base font-semibold text-slate-900 hover:text-slate-900">
            RFQ Auctions
          </NavLink>
          <nav className="order-3 flex w-full gap-1 sm:order-none sm:w-auto" aria-label="Main">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  clsx(
                    "rounded-md px-3 py-1.5 text-sm font-medium",
                    isActive ? "bg-slate-100 text-slate-900" : "text-slate-600 hover:text-slate-900",
                  )
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <ActingSupplierSelect />
          </div>
        </div>
        
        <div className={clsx("h-0.5 bg-accent transition-opacity", navigation.state === "idle" ? "opacity-0" : "opacity-100")} />
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:py-8">
        {health.data && !health.data.redis && (
          <div className="mb-4">
            <Notice tone="warning">Live updates are unavailable; data refreshes periodically.</Notice>
          </div>
        )}
        {health.isError && (
          <div className="mb-4">
            <Notice tone="error" action={<button className="btn-secondary" onClick={() => health.refetch()}>Retry</button>}>
              Cannot reach the server.
            </Notice>
          </div>
        )}
        <Suspense fallback={<Spinner />}>
          <Outlet />
        </Suspense>
      </main>

      <Toaster position="bottom-right" richColors closeButton />
    </div>
  );
}

function ActingSupplierSelect() {
  const { data: suppliers = [] } = useQuery(suppliersQuery());
  const acting = useAppStore((s) => s.actingSupplierId);
  const setActing = useAppStore((s) => s.setActingSupplier);

  return (
    <label className="flex items-center gap-2 text-sm text-slate-600">
      <span className="hidden sm:inline">Acting as</span>
      <select
        className="input w-44 py-1.5"
        value={acting ?? ""}
        onChange={(e) => setActing(e.target.value ? Number(e.target.value) : null)}
        aria-label="Acting as supplier"
      >
        <option value="">Buyer</option>
        {suppliers.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
