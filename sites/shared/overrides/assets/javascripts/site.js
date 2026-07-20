import { enhanceSelect } from "./controls.js";

export function initializeSite() {
  document.querySelectorAll("[data-rw-game-picker]").forEach((picker) => {
    picker.addEventListener("change", () => {
      if (picker.value) window.location.assign(picker.value);
    });
    enhanceSelect(picker, "Choose a game");
  });

  document.querySelectorAll("img[data-rw-sprite]").forEach((image) => {
    image.addEventListener("error", () => {
      image.hidden = true;
      const fallback = image.parentElement.querySelector(".rw-summary__placeholder");
      if (fallback) fallback.hidden = false;
    }, { once: true });
  });
}
