/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * The Application Entry Point. 
 * * This is where the magic starts. It mounts the React application to the 
 * DOM and initializes the 'i18n' translation engine to ensure the app 
 * loads with the correct language (English/Urdu) from the first frame.
 * -------------------------------------------------------------------------
 */

import { createRoot } from "react-dom/client";
import "./i18n";
import App from "./App.tsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(<App />);
