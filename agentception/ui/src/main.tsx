import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(<App />);

// Service Worker handling
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    // Unregister any old service workers to prevent caching issues
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      registrations.forEach((registration) => {
        registration.unregister().then(() => {
          console.log("[SW] Old service worker unregistered");
        });
      });
    });

    // Register new service worker with cache-busting
    navigator.serviceWorker
      .register("/sw.js?v=2")
      .then((registration) => {
        console.log("[SW] Registered:", registration.scope);
      })
      .catch((error) => {
        console.log("[SW] Registration failed:", error);
      });
  });
}
