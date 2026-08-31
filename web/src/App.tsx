import { useEffect, useMemo, useState, useTransition } from "react";
import {
  createGame,
  currentUserId,
  getGame,
  joinGame,
  sendAction,
  startGame,
} from "./api";
import { DiceTray } from "./Dice";
import type { GameState, PlayerState } from "./types";
import { AuthPanel } from "./AuthPanel";

type Mode = "menu" | "solo" | "create" | "join";

function playerTags(p: PlayerState, pits: [number, number][]): string[] {
  const tags: string[] = [];
  if (!p.opened) tags.push("закрыт");
  for (const [low, high] of pits) {
    if (p.score >= low && p.score < high) {
      tags.push("яма");
      break;
    }
  }
  if (p.on_barrel) tags.push("бочка");
  if (p.bolts > 0) tags.push(`болт×${p.bolts}`);
  return tags;
}

function startParamCode(): string | null {
  const raw = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
  if (!raw) return null;
  const m = /^join[_-]?([A-Fa-f0-9]{6})$/i.exec(raw);
  return m ? m[1].toUpperCase() : null;
}

export default function App() {
  const me = useMemo(() => currentUserId(), []);
  const [mode, setMode] = useState<Mode>("menu");
  const [bots, setBots] = useState(1);
  const [maxHumans, setMaxHumans] = useState(2);
  const [joinCode, setJoinCode] = useState("");
  const [game, setGame] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rolling, setRolling] = useState(false);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    const tp = window.Telegram?.WebApp?.themeParams;
    if (!tp) return;
    const root = document.documentElement;
    if (tp.bg_color) root.style.setProperty("--tg-bg", tp.bg_color);
    if (tp.text_color) root.style.setProperty("--tg-text", tp.text_color);
    if (tp.button_color) root.style.setProperty("--tg-button", tp.button_color);
    if (tp.button_text_color) root.style.setProperty("--tg-button-text", tp.button_text_color);
    if (tp.secondary_bg_color) root.style.setProperty("--tg-secondary", tp.secondary_bg_color);
    if (tp.hint_color) root.style.setProperty("--tg-hint", tp.hint_color);
  }, []);

  useEffect(() => {
    const code = startParamCode();
    if (!code) return;
    setMode("join");
    setJoinCode(code);
    void (async () => {
      try {
        setGame(await joinGame(code));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось войти по ссылке");
      }
    })();
  }, []);

  useEffect(() => {
    if (!game) return;
    const myTurn =
      game.status === "playing" && game.players[game.current_player_index]?.id === me;
    const needPoll =
      game.status === "lobby" ||
      (game.status === "playing" && !myTurn && game.phase !== "finished");
    if (!needPoll) return;

    const id = window.setInterval(() => {
      void getGame(game.id)
        .then(setGame)
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(id);
  }, [game, me]);

  const current = game ? game.players[game.current_player_index] : null;
  const isHost = Boolean(game && game.owner_user_id === me);
  const isMyTurn = Boolean(game && current?.id === me);
  const finished = game?.phase === "finished" || game?.status === "finished";
  const inLobby = game?.status === "lobby";

  const canRoll =
    isMyTurn &&
    !finished &&
    !inLobby &&
    !pending &&
    !rolling &&
    (game?.phase === "waiting_roll" || game?.phase === "waiting_decision");

  const canBank =
    isMyTurn &&
    !finished &&
    !inLobby &&
    !pending &&
    !rolling &&
    game?.phase === "waiting_decision" &&
    !game.turn.must_roll &&
    game.turn.can_bank;

  async function startSolo() {
    setError(null);
    try {
      setGame(await createGame(bots, 1));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function createRoom() {
    setError(null);
    try {
      setGame(await createGame(bots, maxHumans));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function doJoin() {
    setError(null);
    try {
      setGame(await joinGame(joinCode.trim().toUpperCase()));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function doStart() {
    if (!game) return;
    setError(null);
    try {
      setGame(await startGame(game.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  function act(type: "roll" | "bank") {
    if (!game) return;
    setError(null);
    if (type === "roll") {
      setRolling(true);
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.("medium");
    }
    startTransition(async () => {
      try {
        if (type === "roll") await new Promise((r) => setTimeout(r, 450));
        setGame(await sendAction(game.id, type));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка хода");
      } finally {
        setRolling(false);
      }
    });
  }

  function reset() {
    setGame(null);
    setMode("menu");
    setError(null);
  }

  async function copyCode() {
    if (!game?.invite_code) return;
    try {
      await navigator.clipboard.writeText(game.invite_code);
      window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred?.("success");
    } catch {
      /* ignore */
    }
  }

  if (!game) {
    return (
      <div className="app">
        <header className="hero">
          <p className="brand">Кости 1000</p>
          <h1>Классика на пять кубиков</h1>
          <p className="lead">Играй с ботами или зови друзей в комнату.</p>
        </header>

        <AuthPanel />

        {mode === "menu" && (
          <section className="lobby">
            <button type="button" className="btn btn--primary" onClick={() => setMode("solo")}>
              Против ботов
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setMode("create")}>
              Создать комнату
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setMode("join")}>
              Войти по коду
            </button>
            {error && <p className="error">{error}</p>}
          </section>
        )}

        {mode === "solo" && (
          <section className="lobby">
            <label className="lobby__label">
              Боты
              <div className="bot-picker">
                {[1, 2, 3].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={bots === n ? "chip chip--active" : "chip"}
                    onClick={() => setBots(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </label>
            <button type="button" className="btn btn--primary" onClick={startSolo}>
              Играть
            </button>
            <button type="button" className="linkish" onClick={() => setMode("menu")}>
              Назад
            </button>
            {error && <p className="error">{error}</p>}
          </section>
        )}

        {mode === "create" && (
          <section className="lobby">
            <label className="lobby__label">
              Мест для людей (включая вас)
              <div className="bot-picker">
                {[2, 3, 4].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={maxHumans === n ? "chip chip--active" : "chip"}
                    onClick={() => setMaxHumans(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </label>
            <label className="lobby__label">
              Боты за столом
              <div className="bot-picker">
                {[0, 1, 2].map((n) => (
                  <button
                    key={n}
                    type="button"
                    className={bots === n ? "chip chip--active" : "chip"}
                    onClick={() => setBots(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </label>
            <button type="button" className="btn btn--primary" onClick={createRoom}>
              Создать
            </button>
            <button type="button" className="linkish" onClick={() => setMode("menu")}>
              Назад
            </button>
            {error && <p className="error">{error}</p>}
          </section>
        )}

        {mode === "join" && (
          <section className="lobby">
            <label className="lobby__label">
              Код комнаты
              <input
                className="code-input"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="ABC123"
                maxLength={12}
              />
            </label>
            <button type="button" className="btn btn--primary" onClick={doJoin}>
              Войти
            </button>
            <button type="button" className="linkish" onClick={() => setMode("menu")}>
              Назад
            </button>
            {error && <p className="error">{error}</p>}
          </section>
        )}
      </div>
    );
  }

  const pits = (game.config?.pits ?? [
    [200, 300],
    [600, 700],
  ]) as [number, number][];
  const recent = game.events.slice(-8).reverse();
  const winner = game.winner_id
    ? game.players.find((p) => p.id === game.winner_id)
    : null;

  if (inLobby) {
    return (
      <div className="app">
        <header className="top">
          <div>
            <p className="brand brand--sm">Кости 1000</p>
            <p className="status-line">Лобби · ждём игроков</p>
          </div>
          <button type="button" className="linkish" onClick={reset}>
            Выйти
          </button>
        </header>

        <section className="lobby">
          <p className="lobby__label">Код комнаты</p>
          <button type="button" className="invite-code" onClick={copyCode}>
            {game.invite_code}
          </button>
          <p className="muted">Нажми код, чтобы скопировать</p>

          <ul className="scores">
            {game.players.map((p) => (
              <li key={p.id} className="scores__row">
                <span className="scores__name">
                  {p.name}
                  {p.id === me ? " (вы)" : ""}
                  {p.kind === "bot" ? " · бот" : ""}
                  {p.id === game.owner_user_id ? " · хост" : ""}
                </span>
              </li>
            ))}
          </ul>
          <p className="muted">
            Люди: {game.players.filter((p) => p.kind === "human").length}/{game.max_humans}
          </p>

          {isHost ? (
            <button type="button" className="btn btn--primary" onClick={doStart}>
              Начать игру
            </button>
          ) : (
            <p className="status-line">Ждём, пока хост начнёт…</p>
          )}
          {error && <p className="error">{error}</p>}
        </section>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="brand brand--sm">Кости 1000</p>
          {finished ? (
            <p className="status-line">Победил {winner?.name ?? "—"}</p>
          ) : (
            <p className="status-line">
              Ход: <strong>{current?.name}</strong>
              {isMyTurn ? " — ваш" : " — ждём"}
            </p>
          )}
        </div>
        <button type="button" className="linkish" onClick={reset}>
          Меню
        </button>
      </header>

      <ul className="scores">
        {game.players.map((p) => {
          const tags = playerTags(p, pits);
          const active = p.id === current?.id;
          return (
            <li
              key={p.id}
              className={active ? "scores__row scores__row--active" : "scores__row"}
            >
              <span className="scores__name">
                {p.name}
                {p.id === me ? " (вы)" : ""}
                {p.kind === "bot" ? " · бот" : ""}
              </span>
              <span className="scores__score">{p.score}</span>
              {tags.length > 0 && <span className="scores__tags">{tags.join(" · ")}</span>}
            </li>
          );
        })}
      </ul>

      <section className="table">
        <DiceTray
          dice={game.turn.last_roll}
          scoring={game.turn.last_scoring_dice}
          rolling={rolling && isMyTurn}
        />
        <div className="turn-meta">
          <div>
            <span className="muted">Ход</span>
            <strong className="turn-score">{game.turn.score}</strong>
          </div>
          <div>
            <span className="muted">Костей</span>
            <strong>{game.turn.remaining_dice}</strong>
          </div>
          {game.turn.last_roll_points > 0 && (
            <div>
              <span className="muted">Бросок</span>
              <strong>+{game.turn.last_roll_points}</strong>
            </div>
          )}
        </div>

        <div className="actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={!canRoll}
            onClick={() => act("roll")}
          >
            {rolling ? "Бросаем…" : "Бросить"}
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!canBank}
            onClick={() => act("bank")}
          >
            Хватит
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="feed" aria-label="События">
        <h2>События</h2>
        <ul>
          {recent.map((e, i) => (
            <li key={`${e.type}-${i}-${e.message}`}>{e.message}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
