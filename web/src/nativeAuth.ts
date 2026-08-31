/** Native shell (iOS/Android) ↔ WebView auth bridge. */

import { loginWithNativeIdToken, setSessionToken } from "./api";
import type { UserProfile } from "./types";

export type NativePlatform = "ios" | "android";

declare global {
  interface Window {
    /** Injected by native WebView before page load. */
    __NATIVE_ID_TOKEN__?: string;
    __NATIVE_PLATFORM__?: NativePlatform;
    /** Called by native after Telegram Login SDK success. */
    TelegramNativeAuth?: {
      submit: (idToken: string, platform?: NativePlatform) => Promise<UserProfile>;
    };
  }
}

function detectPlatform(hint?: string | null): NativePlatform {
  if (hint === "ios" || hint === "android") return hint;
  const ua = navigator.userAgent || "";
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  return "android";
}

function takeTokenFromUrl(): { token: string; platform: NativePlatform } | null {
  try {
    const url = new URL(window.location.href);
    const token =
      url.searchParams.get("native_id_token") ||
      url.searchParams.get("tg_id_token") ||
      url.searchParams.get("id_token");
    if (!token) return null;
    const platform = detectPlatform(url.searchParams.get("platform"));
    url.searchParams.delete("native_id_token");
    url.searchParams.delete("tg_id_token");
    url.searchParams.delete("id_token");
    url.searchParams.delete("platform");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    return { token, platform };
  } catch {
    return null;
  }
}

export async function exchangeNativeIdToken(
  idToken: string,
  platform?: NativePlatform | string | null,
): Promise<UserProfile> {
  const plat = detectPlatform(platform);
  const res = await loginWithNativeIdToken(idToken, plat);
  setSessionToken(res.token);
  return res.user;
}

/**
 * Resolve native auth before the game UI unlocks:
 * 1) window.__NATIVE_ID_TOKEN__ (injected by WebView)
 * 2) ?native_id_token=… query (deep link / openURL)
 * Returns profile if a token was exchanged, otherwise null.
 */
export async function bootstrapNativeAuth(): Promise<UserProfile | null> {
  const injected = window.__NATIVE_ID_TOKEN__;
  if (injected) {
    const platform = window.__NATIVE_PLATFORM__;
    delete window.__NATIVE_ID_TOKEN__;
    delete window.__NATIVE_PLATFORM__;
    return exchangeNativeIdToken(injected, platform);
  }
  const fromUrl = takeTokenFromUrl();
  if (fromUrl) {
    return exchangeNativeIdToken(fromUrl.token, fromUrl.platform);
  }
  return null;
}

export function installNativeAuthBridge(
  onSuccess: (user: UserProfile) => void,
  onError: (message: string) => void,
): () => void {
  const submit = async (idToken: string, platform?: NativePlatform) => {
    const user = await exchangeNativeIdToken(idToken, platform);
    onSuccess(user);
    return user;
  };

  window.TelegramNativeAuth = { submit };

  const onMessage = (event: MessageEvent) => {
    const data = event.data;
    if (!data || typeof data !== "object") return;
    const msg = data as { type?: string; id_token?: string; idToken?: string; platform?: string };
    if (msg.type !== "telegram-native-auth") return;
    const token = msg.id_token || msg.idToken;
    if (!token) return;
    void submit(token, detectPlatform(msg.platform)).catch((e) => {
      onError(e instanceof Error ? e.message : "native auth failed");
    });
  };

  window.addEventListener("message", onMessage);
  return () => {
    window.removeEventListener("message", onMessage);
    if (window.TelegramNativeAuth?.submit === submit) {
      delete window.TelegramNativeAuth;
    }
  };
}
