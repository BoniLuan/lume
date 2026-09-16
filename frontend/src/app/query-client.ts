import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (attempt, error) =>
        !(error instanceof Error && "status" in error && error.status === 401) && attempt < 2,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});
