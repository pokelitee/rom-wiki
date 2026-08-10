import { enhanceSelect } from "./controls.js";

export function initializeSite() {
  document.querySelectorAll("[data-rw-game-picker]").forEach((picker) => {
    const initialize = () => {
      picker.addEventListener("change", () => {
        if (picker.value) window.location.assign(picker.value);
      });
      enhanceSelect(picker, "Choose a game", { popover: true });
    };
    const catalogUrl = picker.dataset.rwGamesUrl;
    if (!catalogUrl || picker.options.length > 1) {
      initialize();
      return;
    }
    fetch(catalogUrl)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("catalog")))
      .then((catalog) => {
        catalog.games.forEach((game) => {
          if (game.id === picker.dataset.rwCurrentGame) return;
          const option = document.createElement("option");
          option.value = `${catalogUrl.replace(/games\.json$/, "")}${game.slug}/`;
          option.textContent = game.name;
          picker.append(option);
        });
      })
      .catch(() => {})
      .finally(initialize);
  });

  document.querySelectorAll("img[data-rw-sprite]").forEach((image) => {
    image.addEventListener("error", () => {
      image.hidden = true;
      const fallback = image.parentElement.querySelector(".rw-summary__placeholder");
      if (fallback) fallback.hidden = false;
    }, { once: true });
  });
}
