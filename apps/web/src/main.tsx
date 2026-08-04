import React from "react";
import ReactDOM from "react-dom/client";
import { PollenToday } from "./pages/PollenToday";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PollenToday />
  </React.StrictMode>,
);
