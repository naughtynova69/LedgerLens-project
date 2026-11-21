import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App.jsx";
import { ErrorBoundary } from "./components/ErrorBoundary.jsx";
import { AccountMemoryProvider } from "./context/AccountMemoryContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AccountMemoryProvider>
        <App />
      </AccountMemoryProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
