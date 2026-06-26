import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

interface QueryProviderProps {
  readonly children: ReactNode;
  readonly client?: QueryClient;
}

export function QueryProvider({
  children,
  client = createQueryClient(),
}: QueryProviderProps) {
  return (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}
