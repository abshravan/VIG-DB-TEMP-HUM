import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserRole } from "../types/api";

interface DecodedToken {
  sub: string;
  role: UserRole;
  exp: number;
}

function decodeToken(token: string): DecodedToken | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  role: UserRole | null;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      username: null,
      role: null,
      setTokens: (accessToken, refreshToken) => {
        const decoded = decodeToken(accessToken);
        set({
          accessToken,
          refreshToken,
          username: decoded?.sub ?? null,
          role: decoded?.role ?? null,
        });
      },
      clear: () => set({ accessToken: null, refreshToken: null, username: null, role: null }),
    }),
    { name: "srm-auth" },
  ),
);
