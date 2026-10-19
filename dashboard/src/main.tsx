import React from "react";
import ReactDOM from "react-dom/client";
import { installAppUpdates } from "./appUpdate";
import App from "./App";
import "./index.css";

// The service worker precaches the app shell so the M&E field tool opens without a network; new builds are fetched
// when the app opens, comes online or resumes, and applied by a reload outside the form (see appUpdate.ts).
installAppUpdates();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
