import { initializeCatalogs } from "./catalog/catalog.js";
import { initializeControls } from "./controls.js";
import { initializeSite } from "./site.js";

// navigation.instant swaps page content without reloading the document, so
// module-level init only runs once. document$ emits on every page render
// (including the first), which keeps filters/tables/etc. working after
// in-app navigation. See https://squidfunk.github.io/mkdocs-material/customization/#additional-javascript
document$.subscribe(() => {
  const theme = document.querySelector('meta[name="romwiki-theme"]');
  if (theme) document.documentElement.dataset.romwikiTheme = theme.content;

  initializeControls();
  initializeSite();
  document.documentElement.classList.add("rw-js", "rw-js-ready");
  initializeCatalogs();
});
