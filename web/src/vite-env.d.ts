/// <reference types="vite/client" />


interface TelegramBottomButton {
  text: string;
  color?: string;
  textColor?: string;
  isVisible?: boolean;
  isActive?: boolean;
  setText: (text: string) => TelegramBottomButton;
  show: () => void;
  hide: () => void;
  onClick: (cb: () => void) => void;
  offClick: (cb: () => void) => void;
  enable: () => void;
  disable: () => void;
  setParams?: (params: {
    text?: string;
    color?: string;
    text_color?: string;
    is_active?: boolean;
    is_visible?: boolean;
  }) => void;
}

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
  close: () => void;
  MainButton: TelegramBottomButton;
  SecondaryButton?: TelegramBottomButton;
  HapticFeedback?: {
    impactOccurred: (style: string) => void;
    notificationOccurred: (type: string) => void;
  };
  requestWriteAccess?: (cb?: (granted: boolean) => void) => void;
  requestContact?: (cb?: (granted: boolean, response?: { responseUnsafe?: { contact?: { phone_number?: string } } }) => void) => void;
  enableClosingConfirmation?: () => void;
  disableClosingConfirmation?: () => void;
  disableVerticalSwipes?: () => void;
}

interface Window {
  Telegram?: { WebApp: TelegramWebApp };
  onTelegramAuth?: (user: Record<string, unknown>) => void;
}
