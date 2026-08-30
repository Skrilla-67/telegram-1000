export type PlayerKind = "human" | "bot";
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
  players: PlayerState[];
  current_player_index: number;
  phase: Phase;
  turn: TurnState;
  events: GameEvent[];
  winner_id: string | null;
  owner_user_id: string | null;
  config: {
    open_threshold: number;
    barrel_threshold: number;
    win_score: number;
    pits: [number, number][];
  };
}
