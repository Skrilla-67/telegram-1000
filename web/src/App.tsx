import { useEffect, useMemo, useState, useTransition } from "react";
import { createGame, sendAction } from "./api";
import { DiceTray } from "./Dice";
import type { GameState, PlayerState } from "./types";

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

export default function App() {
  const [bots, setBots] = useState(1);
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

  const human = useMemo(
    () => game?.players.find((p) => p.kind === "human") ?? null,
    [game],
  );
  const current = game ? game.players[game.current_player_index] : null;
  const isMyTurn = Boolean(game && human && current?.id === human.id);
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

  async function start() {
    setError(null);
    try {
      const state = await createGame(bots);
      setGame(state);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать игру");
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
        // Brief roll animation before applying result.
        if (type === "roll") {
          await new Promise((r) => setTimeout(r, 450));
        }
        const next = await sendAction(game.id, type);
        setGame(next);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка хода");
      } finally {
        setRolling(false);
      }
    });
  }

  if (!game) {
    return (
      <div className="app">
        <header className="hero">
          <p className="brand">Кости 1000</p>
          <h1>Классика на пять кубиков</h1>
          <p className="lead">Открытие, ямы, бочка и боты за одним столом.</p>
        </header>
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
          <button type="button" className="btn btn--primary" onClick={start}>
            Играть
          </button>
          {error && <p className="error">{error}</p>}
        </section>
      </div>
    );
  }

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
        <button type="button" className="linkish" onClick={() => setGame(null)}>
          Новая
        </button>
      </header>

      <ul className="scores">
        {game.players.map((p) => {
          const tags = playerStatus(p, pits);
          const active = p.id === current?.id;
          return (
            <li key={p.id} className={active ? "scores__row scores__row--active" : "scores__row"}>
              <span className="scores__name">
                {p.name}
                {p.kind === "human" ? " (вы)" : ""}
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
