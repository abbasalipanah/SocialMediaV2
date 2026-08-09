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
const localDemoEnabled =
  import.meta.env.DEV && import.meta.env.VITE_LOCAL_DEMO?.trim().toLowerCase() === "true";
let localDemoSessionBootstrap: Promise<void> | null = null;

function openLocalDemoSession(): Promise<void> {
  if (!localDemoSessionBootstrap) {
    localDemoSessionBootstrap = apiCommand("/api/dev/session", {
      method: "POST",
      headers: { "X-Social-Local-Demo": "true" },
    }).catch((error) => {
      localDemoSessionBootstrap = null;
      throw error;
    });
  }
  return localDemoSessionBootstrap;
}

async function currentUser(signal?: AbortSignal): Promise<AuthUser | null> {
  if (localDemoEnabled) {
    await openLocalDemoSession();
    try {
      return await apiQuery("/api/auth/me", authUserSchema, signal);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      // The in-memory local authority is reset whenever the backend reloads.
      // Open a fresh loopback-only session instead of leaving the UI in an
      // unrecoverable connection-error state with a stale cookie.
      localDemoSessionBootstrap = null;
      await openLocalDemoSession();
      return apiQuery("/api/auth/me", authUserSchema, signal);
    }
  }

  try {
    return await apiQuery("/api/auth/me", authUserSchema, signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
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
      await apiCommand(localDemoEnabled ? "/api/dev/logout" : "/api/auth/logout", {
        method: "POST",
        headers: localDemoEnabled ? { "X-Social-Local-Demo": "true" } : undefined,
      });
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
