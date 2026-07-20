import { initializeCatalogs } from "./catalog/catalog.js";
import { initializeControls } from "./controls.js";
import { initializeSite } from "./site.js";

const theme = document.querySelector('meta[name="romwiki-theme"]');
if (theme) document.documentElement.dataset.romwikiTheme = theme.content;

initializeControls();
initializeSite();
document.documentElement.classList.add("rw-js", "rw-js-ready");
initializeCatalogs();
