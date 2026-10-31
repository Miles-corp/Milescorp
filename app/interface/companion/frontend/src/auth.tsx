import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, clearCsrf, errorMessage, setCsrf } from "./api";
import type { Me } from "./types";

interface AuthValue {
  me: Me | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setDevMode: (enabled: boolean) => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const value = await api.me();
      setCsrf(value.csrf_token);
      setMe(value);
      setError(null);
    } catch {
      clearCsrf();
      setMe(null);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .me()
      .then((value) => {
        if (!alive) return;
        setCsrf(value.csrf_token);
        setMe(value);
      })
      .catch(() => {
        if (alive) setMe(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      await api.login(username, password);
      const value = await api.me();
      setMe(value);
    } catch (exc) {
      setError(errorMessage(exc));
      throw exc;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setMe(null);
    }
  }, []);

  const setDevMode = useCallback(async (enabled: boolean) => {
    await api.setDevMode(enabled);
    setMe((current) =>
      current
        ? { ...current, preferences: { ...current.preferences, dev_mode: enabled } }
        : current,
    );
  }, []);

  const value = useMemo(
    () => ({ me, loading, error, login, logout, refresh, setDevMode }),
    [me, loading, error, login, logout, refresh, setDevMode],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return value;
}
