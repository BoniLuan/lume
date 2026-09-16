import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, type PropsWithChildren } from "react";

import { ApiError, api, setCsrfToken } from "../api/client";
import type { Session } from "../api/types";

type SessionContextValue = {
  session: Session | null;
  loading: boolean;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: PropsWithChildren) {
  const result = useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      try {
        return await api<Session>("/api/v1/auth/session");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });

  useEffect(() => setCsrfToken(result.data?.csrf_token), [result.data]);

  return (
    <SessionContext.Provider value={{ session: result.data ?? null, loading: result.isPending }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
