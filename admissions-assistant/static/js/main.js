/**
 * Modular Frontend Entry Point (Phase 3 Remediation).
 * Hydrates dynamic catalog dropdowns from backend DB metadata on page startup.
 */
import { hydrateDynamicCatalogDropdowns } from "./catalog.js";
import { apiFetch, getAuthToken } from "./api.js";

window.SDUModules = {
  apiFetch,
  getAuthToken,
  hydrateDynamicCatalogDropdowns,
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    hydrateDynamicCatalogDropdowns().catch((err) =>
      console.warn("Dynamic catalog hydration warning:", err)
    );
  });
} else {
  hydrateDynamicCatalogDropdowns().catch((err) =>
    console.warn("Dynamic catalog hydration warning:", err)
  );
}
