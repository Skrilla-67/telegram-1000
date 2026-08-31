import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

function bootTelegram() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.enableClosingConfirmation?.();
  tg.disableVerticalSwipes?.();
  // Main Mini App capabilities: write access helps bot features / shared chat tools.
  try {
    tg.requestWriteAccess?.(() => undefined);
  } catch {
    /* older clients */
  }
}

function mount() {
  bootTelegram();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

if (window.Telegram?.WebApp) {
  mount();
} else {
  const started = Date.now();
  const id = window.setInterval(() => {
    if (window.Telegram?.WebApp || Date.now() - started > 1500) {
      window.clearInterval(id);
      mount();
    }
  }, 50);
}
