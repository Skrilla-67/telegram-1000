/// <reference types="vite/client" />

interface TelegramWebAppUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
  allows_write_to_pm?: boolean;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    user?: TelegramWebAppUser;
    start_param?: string;
  };
  ready: () => void;
  expand: () => void;
  platform?: string;
  version?: string;
  themeParams: Record<string, string>;
  colorScheme: "light" | "dark";
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: string) => void;
    notificationOccurred: (type: string) => void;
  };
  requestWriteAccess?: (cb?: (granted: boolean) => void) => void;
  requestContact?: (cb?: (granted: boolean, response?: { responseUnsafe?: { contact?: { phone_number?: string } } }) => void) => void;
  enableClosingConfirmation?: () => void;
  disableVerticalSwipes?: () => void;
}

interface Window {
  Telegram?: { WebApp: TelegramWebApp };
  onTelegramAuth?: (user: Record<string, unknown>) => void;
}
