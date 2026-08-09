import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "../routing";

import { AuthProvider } from "../auth";
import { AppRoutes, ErrorBoundary } from "../routes";

const queryCache = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 0,
    },
  },
});

export function BootstrapApp() {
  return (
    <QueryClientProvider client={queryCache}>
      <BrowserRouter>
        <ErrorBoundary>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
