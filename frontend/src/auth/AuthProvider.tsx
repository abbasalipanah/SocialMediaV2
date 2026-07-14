import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext } from "react";

import { ApiError, apiCommand, apiQuery, authUserSchema, type AuthUser } from "../api";

type AuthContextValue = {
  user: AuthUser | null;
  status: "checking" | "signed_in" | "signed_out" | "error";
  error: Error | null;
  retry: () => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function currentUser(signal?: AbortSignal): Promise<AuthUser | null> {
  try {
    return await apiQuery("/api/auth/me", authUserSchema, signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: ({ signal }) => currentUser(signal),
  });

  const value: AuthContextValue = {
    user: query.data ?? null,
    status: query.isPending
      ? "checking"
      : query.isError
        ? "error"
        : query.data
          ? "signed_in"
          : "signed_out",
    error: query.error,
    retry: () => void query.refetch(),
    logout: async () => {
      await apiCommand("/api/auth/logout", { method: "POST" });
      queryClient.setQueryData(["auth", "me"], null);
      queryClient.removeQueries({ queryKey: ["workspace"] });
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
