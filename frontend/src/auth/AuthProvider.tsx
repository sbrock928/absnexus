import React, { createContext, useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  isModeler: boolean;
  isAdmin: boolean;
  isAnalyst: boolean;
}

export const AuthContext = createContext<AuthCtx>({
  user: null, loading: true, isModeler: false, isAdmin: false, isAnalyst: false,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const role = user?.role ?? "";
  const isModeler = role === "analytics" || role === "admin";
  const isAdmin = role === "admin";
  const isAnalyst = role === "analyst";

  return (
    <AuthContext.Provider value={{ user, loading, isModeler, isAdmin, isAnalyst }}>
      {children}
    </AuthContext.Provider>
  );
}
