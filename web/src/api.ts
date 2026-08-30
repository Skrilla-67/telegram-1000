import type { GameState } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function authHeaders(): HeadersInit {
  const tg = window.Telegram?.WebApp;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  } else {
    headers["X-Dev-User"] = "Dev Player";
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

export function createGame(bots: number): Promise<GameState> {
  return request<GameState>("/api/games", {
    method: "POST",
    body: JSON.stringify({ bots }),
  });
}

export function getGame(id: string): Promise<GameState> {
  return request<GameState>(`/api/games/${id}`);
}

export function sendAction(id: string, type: "roll" | "bank"): Promise<GameState> {
  return request<GameState>(`/api/games/${id}/actions`, {
    method: "POST",
    body: JSON.stringify({ type }),
  });
}
