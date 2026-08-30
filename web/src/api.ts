import type { GameState } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function authHeaders(): HeadersInit {
  const tg = window.Telegram?.WebApp;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  } else {
    let id = localStorage.getItem("dev_user_id");
    if (!id) {
      id = `dev-${Math.random().toString(36).slice(2, 8)}`;
      localStorage.setItem("dev_user_id", id);
    }
    headers["X-Dev-User"] = localStorage.getItem("dev_user_name") || "Dev Player";
    headers["X-Dev-User-Id"] = id;
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
  return localStorage.getItem("dev_user_id") || "dev-user";
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
