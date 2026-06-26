import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryProvider } from "./lib/query";
import AppLayout from "./app/layout";

import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryProvider>
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </QueryProvider>
  </StrictMode>,
);
