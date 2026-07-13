import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { BootstrapApp } from "./app/BootstrapApp";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Application root is missing");
}

createRoot(root).render(
  <StrictMode>
    <BootstrapApp />
  </StrictMode>,
);
