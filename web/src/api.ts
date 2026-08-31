import type { GameState, GameHistoryItem, UserProfile } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const SESSION_KEY = "tg_session_token";

export function getSessionToken(): string | null {
  return localStorage.getItem(SESSION_KEY);
}

export function setSessionToken(token: string | null) {
  if (!token) localStorage.removeItem(SESSION_KEY);
  else localStorage.setItem(SESSION_KEY, token);
}

function clientMeta(): Record<string, unknown> {
  const tg = window.Telegram?.WebApp;
  if (!tg) return {};
  const u = tg.initDataUnsafe?.user;
  return {
    platform: tg.platform,
    tg_version: tg.version,
    color_scheme: tg.colorScheme,
    allows_write_to_pm: u?.allows_write_to_pm,
    language_code: u?.language_code,
    is_premium: u?.is_premium,
    photo_url: u?.photo_url,
  };
}

function authHeaders(): HeadersInit {
  const tg = window.Telegram?.WebApp;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const meta = clientMeta();
  if (Object.keys(meta).length) {
    headers["X-Client-Meta"] = JSON.stringify(meta);
  }
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  } else {
    const session = getSessionToken();
    if (session) {
      headers["Authorization"] = `Bearer ${session}`;
      headers["X-Session-Token"] = session;
    } else {
      let id = localStorage.getItem("dev_user_id");
      if (!id) {
        id = `dev-${Math.random().toString(36).slice(2, 8)}`;
        localStorage.setItem("dev_user_id", id);
      }
      headers["X-Dev-User"] = localStorage.getItem("dev_user_name") || "Dev Player";
      headers["X-Dev-User-Id"] = id;
    }
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export function currentUserId(): string {
  const uid = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (uid) return String(uid);
  const session = getSessionToken();
  if (session) {
    try {
      const body = session.split(".")[0];
      const padded = body + "=".repeat((4 - (body.length % 4)) % 4);
      const json = JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/")));
      if (json.uid) return String(json.uid);
    } catch {
      /* ignore */
    }
  }
  return localStorage.getItem("dev_user_id") || "dev-user";
}

export function fetchConfig(): Promise<{ bot_username: string; webapp_url: string; dev_mode: boolean }> {
  return request("/api/config");
}

export function loginWithTelegramWidget(payload: Record<string, unknown>): Promise<{ token: string; user: UserProfile }> {
  return request("/api/auth/telegram", { method: "POST", body: JSON.stringify(payload) });
}

export function fetchMe(): Promise<UserProfile> {
  return request("/api/me");
}

export function pingMe(extra?: Record<string, unknown>): Promise<UserProfile> {
  return request("/api/me/ping", { method: "POST", body: JSON.stringify({ ...clientMeta(), ...extra }) });
}

export function fetchHistory(): Promise<{ items: GameHistoryItem[] }> {
  return request("/api/me/history");
}

export function createGame(bots: number, maxHumans = 1): Promise<GameState> {
  return request("/api/games", {
    method: "POST",
    body: JSON.stringify({ bots, max_humans: maxHumans }),
  });
}

export function joinGame(code: string): Promise<GameState> {
  return request("/api/games/join", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function startGame(id: string): Promise<GameState> {
  return request(`/api/games/${id}/start`, { method: "POST" });
}

export function getGame(id: string): Promise<GameState> {
  return request(`/api/games/${id}`);
}

export function sendAction(id: string, type: "roll" | "bank"): Promise<GameState> {
  return request(`/api/games/${id}/actions`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}
