import { useEffect } from "react";

const PLAY_RED = "#d32f2f";
const PLAY_TEXT = "#ffffff";
const BAIL_BLUE = "#1565c0";
const BAIL_TEXT = "#ffffff";

function configureButton(
  btn: NonNullable<Window["Telegram"]>["WebApp"]["MainButton"],
  text: string,
  color: string,
  textColor: string,
) {
  if (btn.setParams) {
    btn.setParams({
      text,
      color,
      text_color: textColor,
      is_active: true,
      is_visible: true,
    });
  } else {
    btn.setText(text);
    btn.color = color;
    btn.textColor = textColor;
  }
  btn.show();
  btn.enable();
}

export function useTelegramMenuButtons(
  active: boolean,
  onPlay: () => void,
  onBail: () => void,
) {
  useEffect(() => {
    if (!active) return;
    const tg = window.Telegram?.WebApp;
    if (!tg) return;

    const main = tg.MainButton;
    const secondary = tg.SecondaryButton;
    configureButton(main, "Го катку", PLAY_RED, PLAY_TEXT);
    main.onClick(onPlay);

    if (secondary) {
      configureButton(secondary, "Слиться", BAIL_BLUE, BAIL_TEXT);
      secondary.onClick(onBail);
    }

    return () => {
      main.offClick(onPlay);
      main.hide();
      if (secondary) {
        secondary.offClick(onBail);
        secondary.hide();
      }
    };
  }, [active, onPlay, onBail]);
}

export function closeMiniApp() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;
  tg.disableClosingConfirmation?.();
  tg.close();
}
