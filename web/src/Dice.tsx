const PIP_MAP: Record<number, number[]> = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
};

type Props = {
  value: number;
  scoring?: boolean;
  rolling?: boolean;
};

export function Die({ value, scoring, rolling }: Props) {
  const pips = PIP_MAP[value] ?? [];
  return (
    <div
      className={`die ${scoring ? "die--scoring" : ""} ${rolling ? "die--rolling" : ""}`}
      aria-label={`Кубик ${value}`}
    >
      <div className="die__face">
        {Array.from({ length: 9 }, (_, i) => (
          <span key={i} className={`pip ${pips.includes(i) ? "pip--on" : ""}`} />
        ))}
      </div>
    </div>
  );
}

type TrayProps = {
  dice: number[];
  scoring: number[];
  rolling: boolean;
};

export function DiceTray({ dice, scoring, rolling }: TrayProps) {
  const scoringCopy = [...scoring];
  return (
    <div className="dice-tray">
      {(dice.length ? dice : [0, 0, 0, 0, 0]).map((v, i) => {
        let isScoring = false;
        if (v > 0 && scoringCopy.length) {
          const idx = scoringCopy.indexOf(v);
          if (idx >= 0) {
            scoringCopy.splice(idx, 1);
            isScoring = true;
          }
        }
        return (
          <Die
            key={`${i}-${v}-${rolling}`}
            value={v || 1}
            scoring={isScoring && !rolling}
            rolling={rolling}
          />
        );
      })}
    </div>
  );
}
