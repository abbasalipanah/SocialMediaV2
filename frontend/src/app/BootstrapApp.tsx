import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { APP_BOOTSTRAP_MODE } from "./bootstrap";

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
        <main className="bootstrap" data-runtime-mode={APP_BOOTSTRAP_MODE}>
          <p className="eyebrow">Social Media V2</p>
          <h1>Safe bootstrap is ready.</h1>
          <p>Product routes remain dormant until their phase gates pass.</p>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
