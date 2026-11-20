import "@fontsource-variable/inter";
// linting error
import "./index.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { ApiError } from "./api/client";
import { rfqDetailQuery } from "./api/queries";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
});

const router = createBrowserRouter([
  {
    element: <Layout />,
    HydrateFallback: Spinner,
    children: [
      { index: true, element: <Navigate to="/auctions" replace /> },
      { path: "auctions", lazy: () => import("./pages/AuctionListPage") },
      { path: "auctions/new", lazy: () => import("./pages/CreateRfqPage") },
      {
        path: "auctions/:id",
        loader: ({ params }) => {
          const id = Number(params.id);
          if (Number.isInteger(id) && id > 0) void queryClient.prefetchQuery(rfqDetailQuery(id));
          return null;
        },
        lazy: () => import("./pages/AuctionDetailPage"),
      },
      { path: "suppliers", lazy: () => import("./pages/SuppliersPage") },
      { path: "*", lazy: () => import("./pages/NotFoundPage") },
    ],
  },
]);

const Devtools = import.meta.env.DEV
  ? lazy(() => import("@tanstack/react-query-devtools").then((m) => ({ default: m.ReactQueryDevtools })))
  : () => null;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Suspense>
        <Devtools />
      </Suspense>
    </QueryClientProvider>
  </StrictMode>,
);
