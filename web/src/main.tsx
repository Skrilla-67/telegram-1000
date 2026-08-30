import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

function bootTelegram() {
  const tg = window.Telegram?.WebApp;
  tg?.ready();
  tg?.expand();
}

function mount() {
  bootTelegram();
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

// Если SDK ещё грузится (async), подождём коротко; иначе сразу монтируем UI.
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
