import { useEffect, useState } from "react";
import {
  fetchConfig,
  fetchHistory,
  fetchMe,
  getSessionToken,
  loginWithTelegramWidget,
  pingMe,
  setSessionToken,
} from "./api";
import type { GameHistoryItem, UserProfile } from "./types";

declare global {
  interface Window {
    onTelegramAuth?: (user: Record<string, unknown>) => void;
  }
}

export function AuthPanel() {
  const inTelegram = Boolean(window.Telegram?.WebApp?.initData);
  const [botUsername, setBotUsername] = useState("");
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<GameHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const cfg = await fetchConfig();
        setBotUsername(cfg.bot_username);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        if (inTelegram || getSessionToken()) {
          setProfile(await pingMe());
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "auth error");
      }
    })();
  }, [inTelegram]);

  useEffect(() => {
    if (inTelegram) return;
    if (!botUsername) return;
    if (getSessionToken()) return;

    window.onTelegramAuth = (user) => {
      void (async () => {
        try {
          const res = await loginWithTelegramWidget(user);
          setSessionToken(res.token);
          setProfile(res.user);
          setError(null);
          // remove widget after login
          const mount = document.getElementById("tg-login-slot");
          if (mount) mount.innerHTML = "";
        } catch (e) {
          setError(e instanceof Error ? e.message : "login failed");
        }
      })();
    };

    const slot = document.getElementById("tg-login-slot");
    if (!slot || slot.childElementCount > 0) return;
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "10");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    slot.appendChild(script);

    return () => {
      window.onTelegramAuth = undefined;
    };
  }, [botUsername, inTelegram, profile]);

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
        .then(setProfile)
        .catch(() => undefined);
    });
  }

  async function askWrite() {
    const tg = window.Telegram?.WebApp;
    if (!tg?.requestWriteAccess) return;
    tg.requestWriteAccess(() => {
      void pingMe().then(setProfile).catch(() => undefined);
    });
  }

  function logout() {
    setSessionToken(null);
    setProfile(null);
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
                  <strong>{h.winner_name ?? "—"}</strong>
                  <span className="muted">
                    {" "}
                    · {new Date(h.finished_at * 1000).toLocaleString()} · код {h.invite_code || "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="auth-card">
          <p className="auth-name">Вход через Telegram</p>
          <p className="muted">Логин-виджет на сайте и полный доступ Mini App.</p>
          {!inTelegram && <div id="tg-login-slot" className="tg-login-slot" />}
          {inTelegram && (
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void fetchMe().then(setProfile)}
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
