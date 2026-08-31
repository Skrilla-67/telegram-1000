export type PlayerKind = "human" | "bot";
export type GameStatus = "lobby" | "playing" | "finished";
export type Phase = "waiting_roll" | "waiting_decision" | "finished";

export interface PlayerState {
  id: string;
  name: string;
  kind: PlayerKind;
  score: number;
  opened: boolean;
  bolts: number;
  on_barrel: boolean;
  barrel_attempts: number;
  barrel_falls: number;
}

export interface TurnState {
  score: number;
  remaining_dice: number;
  last_roll: number[];
  last_scoring_dice: number[];
  last_roll_points: number;
  can_bank: boolean;
  must_roll: boolean;
}

export interface GameEvent {
  type: string;
  message: string;
  data: Record<string, unknown>;
}

export interface GameState {
  id: string;
  invite_code: string;
  status: GameStatus;
  players: PlayerState[];
  max_humans: number;
  current_player_index: number;
  phase: Phase;
  turn: TurnState;
  events: GameEvent[];
  winner_id: string | null;
  owner_user_id: string | null;
  config: {
    open_threshold?: number;
    barrel_threshold?: number;
    win_score?: number;
    pits?: [number, number][];
  };
}


export interface UserProfile {
  id: string;
  first_name: string;
  last_name?: string | null;
  username?: string | null;
  language_code?: string | null;
  is_premium?: boolean | null;
  photo_url?: string | null;
  allows_write_to_pm?: boolean | null;
  phone_number?: string | null;
  platform?: string | null;
  tg_version?: string | null;
  color_scheme?: string | null;
  auth_sources: string[];
  first_seen_at: number;
  last_seen_at: number;
  games_played: number;
  games_won: number;
  extra?: Record<string, unknown>;
}

export interface GameHistoryItem {
  game_id: string;
  finished_at: number;
  invite_code: string;
  winner_id: string | null;
  winner_name: string | null;
  players: { id: string; name: string; kind: string; score: number }[];
  human_ids: string[];
  max_humans: number;
  status: string;
}
