const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getStoredTokens() {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("noram_access_token"),
    refresh: localStorage.getItem("noram_refresh_token"),
  };
}

export function setStoredTokens(access: string, refresh: string) {
  localStorage.setItem("noram_access_token", access);
  localStorage.setItem("noram_refresh_token", refresh);
}

export function clearStoredTokens() {
  localStorage.removeItem("noram_access_token");
  localStorage.removeItem("noram_refresh_token");
}

async function tryRefresh(): Promise<string | null> {
  const { refresh } = getStoredTokens();
  if (!refresh) return null;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      clearStoredTokens();
      return null;
    }
    const data = await res.json();
    setStoredTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { skipAuth?: boolean; terminalToken?: string } = {}
): Promise<T> {
  const { skipAuth, terminalToken, headers, ...rest } = options;
  const reqHeaders = new Headers(headers);

  if (!(rest.body instanceof FormData) && !reqHeaders.has("Content-Type")) {
    reqHeaders.set("Content-Type", "application/json");
  }

  if (terminalToken) {
    reqHeaders.set("X-Terminal-Token", terminalToken);
  } else if (!skipAuth) {
    const { access } = getStoredTokens();
    if (access) {
      reqHeaders.set("Authorization", `Bearer ${access}`);
    }
  }

  let res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: reqHeaders,
  });

  if (res.status === 401 && !skipAuth && !terminalToken) {
    const newAccess = await tryRefresh();
    if (newAccess) {
      reqHeaders.set("Authorization", `Bearer ${newAccess}`);
      res = await fetch(`${API_BASE}${path}`, {
        ...rest,
        headers: reqHeaders,
      });
    }
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let code: string | undefined;
    try {
      const errData = await res.json();
      message = errData.detail || message;
      code = errData.code;
    } catch {
      // ignore parse error
    }
    throw new ApiError(message, res.status, code);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const { access } = getStoredTokens();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (!res.ok) {
    throw new ApiError("Failed to download file", res.status);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
