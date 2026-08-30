import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import {
  createGame,
  createRoom,
  currentUserId,
  getGame,
  getRoom,
  joinRoom,
  sendAction,
  startRoom,
} from "./api";
import { DiceTray } from "./Dice";
import type { GameState, PlayerState, RoomView } from "./types";

type LobbyMode = "menu" | "solo" | "create" | "join";

function playerStatus(p: PlayerState, pits: [number, number][]): string[] {
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

function readInviteCode(): string | null {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("room");
  if (fromQuery) return fromQuery.trim().toUpperCase();
  const start = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
  if (start) return start.trim().toUpperCase();
  return null;
}

function inviteUrl(code: string): string {
  const url = new URL(window.location.href);
  url.searchParams.set("room", code);
  // Keep dev identity params if present for local multi-tab testing.
  return url.toString();
}

export default function App() {
  const [mode, setMode] = useState<LobbyMode>("menu");
  const [bots, setBots] = useState(1);
  const [roomBots, setRoomBots] = useState(1);
  const [maxHumans, setMaxHumans] = useState(2);
  const [joinCode, setJoinCode] = useState("");
  const [room, setRoom] = useState<RoomView | null>(null);
  const [game, setGame] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rolling, setRolling] = useState(false);
  const [copied, setCopied] = useState(false);
  const [pending, startTransition] = useTransition();
  const [autoJoinTried, setAutoJoinTried] = useState(false);
  const me = useMemo(() => currentUserId(), []);
  const pollRef = useRef<number | null>(null);

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

  // Auto-join from ?room= or Telegram startapp
  useEffect(() => {
    if (autoJoinTried || game || room) return;
    const code = readInviteCode();
    if (!code) {
      setAutoJoinTried(true);
      return;
    }
    setAutoJoinTried(true);
    setJoinCode(code);
    setMode("join");
    (async () => {
      try {
        const view = await joinRoom(code);
        setRoom(view);
        if (view.game) setGame(view.game);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось войти в комнату");
      }
    })();
  }, [autoJoinTried, game, room]);

  // Poll multiplayer room (~1s)
  useEffect(() => {
    if (!room || room.status === "finished") {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    const code = room.code;
    const tick = async () => {
      try {
        const view = await getRoom(code);
        setRoom(view);
        if (view.game) {
          setGame(view.game);
        } else if (view.game_id) {
          const g = await getGame(view.game_id);
          setGame(g);
        }
      } catch {
        /* ignore transient poll errors */
      }
    };

    pollRef.current = window.setInterval(tick, 1000);
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [room?.code, room?.status]);

  const mySeat = useMemo(() => {
    if (!game) return null;
    return game.players.find((p) => p.kind === "human" && p.id === me) ?? null;
  }, [game, me]);

  const current = game ? game.players[game.current_player_index] : null;
  const isMyTurn = Boolean(game && mySeat && current?.id === mySeat.id);
  const finished = game?.phase === "finished";

  const canRoll =
    isMyTurn &&
    !finished &&
    !pending &&
    !rolling &&
    (game?.phase === "waiting_roll" || game?.phase === "waiting_decision");

  const canBank =
    isMyTurn &&
    !finished &&
    !pending &&
    !rolling &&
    game?.phase === "waiting_decision" &&
    !game.turn.must_roll &&
    game.turn.can_bank;

  function resetToMenu() {
    setGame(null);
    setRoom(null);
    setMode("menu");
    setError(null);
    setCopied(false);
  }

  async function startSolo() {
    setError(null);
    try {
      const state = await createGame(bots);
      setRoom(null);
      setGame(state);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать игру");
    }
  }

  async function doCreateRoom() {
    setError(null);
    try {
      const view = await createRoom(roomBots, maxHumans);
      setRoom(view);
      setGame(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать комнату");
    }
  }

  async function doJoinRoom() {
    setError(null);
    try {
      const view = await joinRoom(joinCode);
      setRoom(view);
      if (view.game) setGame(view.game);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось войти");
    }
  }

  async function doStartRoom() {
    if (!room) return;
    setError(null);
    try {
      const view = await startRoom(room.code);
      setRoom(view);
      if (view.game) setGame(view.game);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось начать");
    }
  }

  async function copyInvite() {
    if (!room) return;
    const text = inviteUrl(room.code);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(`Ссылка: ${text}`);
    }
  }

  function act(type: "roll" | "bank") {
    if (!game) return;
    setError(null);
    if (type === "roll") {
      setRolling(true);
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred("medium");
    }
    startTransition(async () => {
      try {
        if (type === "roll") {
          await new Promise((r) => setTimeout(r, 450));
        }
        const next = await sendAction(game.id, type);
        setGame(next);
        if (room) {
          setRoom({ ...room, game: next, status: next.phase === "finished" ? "finished" : room.status });
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка хода");
      } finally {
        setRolling(false);
      }
    });
  }

  // —— Waiting room ——
  if (room && room.status === "lobby") {
    const canStart = room.you_are_host && room.seats.length + room.bots >= 2;
    return (
      <div className="app">
        <header className="top">
          <div>
            <p className="brand brand--sm">Кости 1000</p>
            <p className="status-line">Комната ожидания</p>
          </div>
          <button type="button" className="linkish" onClick={resetToMenu}>
            Выйти
          </button>
        </header>

        <section className="waiting">
          <div className="code-block">
            <span className="muted">Код</span>
            <strong className="room-code">{room.code}</strong>
            <button type="button" className="btn btn--ghost" onClick={copyInvite}>
              {copied ? "Скопировано" : "Ссылка"}
            </button>
          </div>

          <p className="muted">
            Места: {room.seats.length}/{room.max_humans} · боты: {room.bots}
          </p>

          <ul className="seat-list">
            {room.seats.map((s) => (
              <li key={s.user_id}>
                <span>
                  {s.name}
                  {s.user_id === me ? " (вы)" : ""}
                  {s.user_id === room.host_id ? " · хост" : ""}
                </span>
                <span className="tag">человек</span>
              </li>
            ))}
            {Array.from({ length: room.bots }, (_, i) => (
              <li key={`bot-${i}`}>
                <span>Бот {i + 1}</span>
                <span className="tag">бот</span>
              </li>
            ))}
          </ul>

          {room.you_are_host ? (
            <button
              type="button"
              className="btn btn--primary"
              disabled={!canStart}
              onClick={doStartRoom}
            >
              Начать игру
            </button>
          ) : (
            <p className="waiting-note">Ждём, пока хост начнёт игру…</p>
          )}
          {error && <p className="error">{error}</p>}
        </section>
      </div>
    );
  }

  // —— Active / finished table ——
  if (game) {
    const pits = (game.config.pits ?? [
      [200, 300],
      [600, 700],
    ]) as [number, number][];
    const recent = game.events.slice(-8).reverse();
    const winner = game.winner_id
      ? game.players.find((p) => p.id === game.winner_id)
      : null;

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
                {isMyTurn ? " — ваш" : ""}
              </p>
            )}
          </div>
          <button type="button" className="linkish" onClick={resetToMenu}>
            {room ? "В лобби" : "Новая"}
          </button>
        </header>

        <ul className="scores">
          {game.players.map((p) => {
            const tags = playerStatus(p, pits);
            const active = p.id === current?.id;
            const isMe = p.id === me;
            return (
              <li key={p.id} className={active ? "scores__row scores__row--active" : "scores__row"}>
                <span className="scores__name">
                  {p.name}
                  {isMe ? " (вы)" : p.kind === "bot" ? "" : ""}
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
            rolling={rolling}
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

          {!finished && !isMyTurn && (
            <p className="waiting-note">
              {current?.kind === "bot" ? "Ход бота…" : `Ход игрока ${current?.name}`}
            </p>
          )}

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

  // —— Lobby ——
  return (
    <div className="app">
      <header className="hero">
        <p className="brand">Кости 1000</p>
        <h1>Классика на пять кубиков</h1>
        <p className="lead">Открытие, ямы, бочка — с друзьями или против ботов.</p>
      </header>

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
            Соперники-боты
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
            Боты за столом
            <div className="bot-picker">
              {[0, 1, 2, 3].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={roomBots === n ? "chip chip--active" : "chip"}
                  onClick={() => setRoomBots(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          </label>
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
          <button type="button" className="btn btn--primary" onClick={doCreateRoom}>
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
              maxLength={8}
              autoCapitalize="characters"
            />
          </label>
          <button
            type="button"
            className="btn btn--primary"
            disabled={joinCode.trim().length < 4}
            onClick={doJoinRoom}
          >
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
