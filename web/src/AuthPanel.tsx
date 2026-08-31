import { useEffect, useState } from "react";
import {
  fetchConfig,
  fetchHistory,
  fetchMe,
  getSessionToken,
  loginWithOidc,
  loginWithTelegramWidget,
  pingMe,
  setSessionToken,
} from "./api";
import { bootstrapNativeAuth, installNativeAuthBridge } from "./nativeAuth";
import type { GameHistoryItem, UserProfile } from "./types";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

type Props = {
  onAuthChange?: (user: UserProfile | null) => void;
};

export function AuthPanel({ onAuthChange }: Props) {
  const inTelegram = Boolean(window.Telegram?.WebApp?.initData);
  const [botUsername, setBotUsername] = useState("");
  const [botClientId, setBotClientId] = useState("");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<GameHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booting, setBooting] = useState(true);

  function applyProfile(user: UserProfile | null) {
    setProfile(user);
    onAuthChange?.(user);
  }

  useEffect(() => {
    void (async () => {
      try {
        const cfg = await fetchConfig();
        setBotUsername(cfg.bot_username);
        setBotClientId(cfg.bot_client_id || "");
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    const uninstall = installNativeAuthBridge(
      (user) => {
        applyProfile(user);
        setError(null);
      },
      (message) => setError(message),
    );

    void (async () => {
      try {
        const nativeUser = await bootstrapNativeAuth();
        if (nativeUser) {
          applyProfile(nativeUser);
          setError(null);
          return;
        }
        if (inTelegram || getSessionToken()) {
          applyProfile(await pingMe());
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "auth error");
      } finally {
        setBooting(false);
      }
    })();

    return uninstall;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inTelegram]);

  useEffect(() => {
    if (inTelegram) return;
    if (booting) return;
    if (!botClientId && !botUsername) return;
    if (getSessionToken() || profile) return;

    window.onTelegramAuth = (data) => {
      void (async () => {
        try {
          const payload = data as Record<string, unknown>;
          const res = payload.id_token
            ? await loginWithOidc(String(payload.id_token))
            : await loginWithTelegramWidget(payload as Record<string, unknown>);
          setSessionToken(res.token);
          applyProfile(res.user);
          setError(null);
          const mount = document.getElementById("tg-login-slot");
          if (mount) mount.innerHTML = "";
        } catch (e) {
          setError(e instanceof Error ? e.message : "login failed");
        }
      })();
    };

    const slot = document.getElementById("tg-login-slot");
    if (!slot) return;

    slot.innerHTML = "";
    const loginName = botUsername.replace(/^@/, "");

    if (loginName) {
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://telegram.org/js/telegram-widget.js?22";
      script.setAttribute("data-telegram-login", loginName);
      script.setAttribute("data-size", "large");
      script.setAttribute("data-radius", "10");
      script.setAttribute("data-onauth", "onTelegramAuth(user)");
      script.setAttribute("data-request-access", "write");
      slot.appendChild(script);
    } else if (botClientId) {
      const script = document.createElement("script");
      script.async = true;
      script.src = "https://oauth.telegram.org/js/telegram-login.js?6";
      script.setAttribute("data-client-id", botClientId);
      script.setAttribute("data-onauth", "onTelegramAuth(data)");
      script.setAttribute("data-request-access", "write");
      slot.appendChild(script);
    }

    return () => {
      window.onTelegramAuth = undefined;
      slot.innerHTML = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botClientId, botUsername, inTelegram, profile, booting]);

  async function loadHistory() {
    setShowHistory(true);
    try {
      const res = await fetchHistory();
      setHistory(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "history error");
    }
  }

  async function askContact() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.requestContact) return;
    tg.requestContact((granted, response) => {
      if (!granted) return;
      const phone = response?.responseUnsafe?.contact?.phone_number;
      void pingMe(phone ? { phone_number: phone } : undefined)
        .then(applyProfile)
        .catch(() => undefined);
    });
  }

  async function askWrite() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.requestWriteAccess) return;
    tg.requestWriteAccess(() => {
      void pingMe().then(applyProfile).catch(() => undefined);
    });
  }

  function logout() {
    setSessionToken(null);
    applyProfile(null);
    setHistory([]);
  }

  return (
    <section className="auth-panel">
      {profile ? (
        <div className="auth-card">
          <div className="auth-card__row">
            {profile.photo_url ? (
              <img className="auth-avatar" src={profile.photo_url} alt="" />
            ) : (
              <div className="auth-avatar auth-avatar--ph" />
            )}
            <div>
              <p className="auth-name">
                {profile.username ? `@${profile.username}` : profile.first_name}
              </p>
              <p className="muted auth-meta">
                id {profile.id}
                {profile.is_premium ? " · premium" : ""}
                {profile.language_code ? ` · ${profile.language_code}` : ""}
              </p>
              <p className="muted auth-meta">
                игр {profile.games_played} · побед {profile.games_won}
              </p>
            </div>
          </div>
          <div className="auth-actions">
            <button type="button" className="btn btn--ghost" onClick={() => void loadHistory()}>
              История
            </button>
            {inTelegram && (
              <>
                <button type="button" className="btn btn--ghost" onClick={() => void askWrite()}>
                  Писать в ЛС
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => void askContact()}>
                  Контакт
                </button>
              </>
            )}
            {!inTelegram && (
              <button type="button" className="linkish" onClick={logout}>
                Выйти
              </button>
            )}
          </div>
          {showHistory && (
            <ul className="history-list">
              {history.length === 0 && <li className="muted">Пока пусто</li>}
              {history.map((h) => (
                <li key={h.game_id}>
                  <strong>{h.winner_name ?? "-"}</strong>
                  <span className="muted">
                    {" "}
                    · {new Date(h.finished_at * 1000).toLocaleString()} · код{" "}
                    {h.invite_code || "-"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="auth-card">
          <p className="auth-name">Вход через Telegram</p>
          <p className="muted">
            {booting
              ? "Проверяем авторизацию…"
              : "Войдите, чтобы начать игру. На телефоне — нативный Login SDK, на сайте — виджет."}
          </p>
          {!booting && !botUsername && !botClientId && (
            <p className="muted">Загружаем настройки бота…</p>
          )}
          {!booting && (botUsername || botClientId) && (
            <p className="muted widget-hint">
              Если кнопки нет: BotFather → /setdomain → домен сайта (например
              telegram-1000-web.onrender.com).
            </p>
          )}
          {!inTelegram && !booting && <div id="tg-login-slot" className="tg-login-slot" />}
          {inTelegram && !booting && (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void fetchMe().then(applyProfile)}
            >
              Продолжить в Mini App
            </button>
          )}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}
