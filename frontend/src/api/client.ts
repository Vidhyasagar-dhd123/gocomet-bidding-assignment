export const DEFAULT_VALIDATION_MESSAGE = "Please correct the highlighted fields";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    public details?: unknown,
    public fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | undefined | null>;

function buildUrl(path: string, query?: Query) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  const s = qs.toString();
  return `${BASE}${path}${s ? `?${s}` : ""}`;
}
async function toApiError(res: Response): Promise<ApiError> {
  const body = await res.json().catch(() => ({}));
  if (body?.error) return new ApiError(res.status, body.error.message, body.error.code, body.error.details);
  if (Array.isArray(body?.detail)) {
    const fieldErrors: Record<string, string> = {};
    let formMessage = "";
    for (const d of body.detail) {
      const msg = String(d.msg).replace(/^Value error, /, "");
      const field = d.loc?.[0] === "body" ? d.loc[1] : undefined;
      if (typeof field === "string") fieldErrors[field] = msg;
      else formMessage ||= msg;
    }
    return new ApiError(res.status, formMessage || DEFAULT_VALIDATION_MESSAGE, "request_validation", body.detail, fieldErrors);
  }
  return new ApiError(res.status, res.status >= 500 ? "Server error, please try again" : `Request failed (${res.status})`);
}

async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown; signal?: AbortSignal } = {}) {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method,
      signal: opts.signal,
      headers: opts.body ? { "Content-Type": "application/json" } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the server");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

export const http = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>("GET", path, { query, signal }),
  post: <T>(path: string, body: unknown) => request<T>("POST", path, { body }),
};

export const streamUrl = (path: string) => `${BASE}${path}`;
