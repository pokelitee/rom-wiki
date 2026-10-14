import { initializeCatalogs } from "./catalog/catalog.js";
import { initializeControls } from "./controls.js";
import { initializeLearnerTables } from "./learner-tables.js";
import { initializeSite } from "./site.js";

const COLOR_SCHEME_STORAGE_KEY = "romwiki.color-scheme";

function initializeColorSchemePreference() {
  const palette = document.querySelector('[data-md-component="palette"]');
  if (!palette || palette.dataset.rwInitialized) return;

  palette.dataset.rwInitialized = "true";
  palette.addEventListener("change", (event) => {
    const input = event.target.closest('input[data-md-color-scheme]');
    if (!input) return;

    try {
      localStorage.setItem(COLOR_SCHEME_STORAGE_KEY, input.dataset.mdColorScheme);
    } catch (error) {
      // The active page still changes scheme when storage is unavailable.
    }
  });
}

// document$ is Material's supported hook for per-page initialization: it emits
// once the document is ready after Material's bundle has loaded. Instant
// navigation is intentionally disabled (see docs/development/frontend.md), but
// if it were enabled document$ would also emit after each in-place page swap.
// See https://squidfunk.github.io/mkdocs-material/customization/#additional-javascript
document$.subscribe(() => {
  const theme = document.querySelector('meta[name="romwiki-theme"]');
  if (theme) document.documentElement.dataset.romwikiTheme = theme.content;

  initializeControls();
  initializeSite();
  initializeColorSchemePreference();
  document.documentElement.classList.add("rw-js", "rw-js-ready");
  initializeLearnerTables();
  initializeCatalogs();
});
