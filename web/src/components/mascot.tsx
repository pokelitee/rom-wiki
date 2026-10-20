import { useEffect, useState } from "react";

const trimmed = new Map<string, Promise<string>>();

// Sprites sit in a mostly empty 96px canvas; cropping to the drawn pixels
// lets the Pokémon fill a small tile. Falls back to the sprite as published
// when its host does not allow reading the pixels.
function trim(url: string): Promise<string> {
  const cached = trimmed.get(url);
  if (cached) return cached;
  const result = new Promise<string>((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;
        const context = canvas.getContext("2d");
        if (!context) return resolve(url);
        context.drawImage(image, 0, 0);
        const { data, width, height } = context.getImageData(
          0,
          0,
          canvas.width,
          canvas.height,
        );
        let [left, top, right, bottom] = [width, height, -1, -1];
        for (let y = 0; y < height; y++)
          for (let x = 0; x < width; x++)
            if (data[(y * width + x) * 4 + 3] > 0) {
              left = Math.min(left, x);
              right = Math.max(right, x);
              top = Math.min(top, y);
              bottom = Math.max(bottom, y);
            }
        if (right < 0) return resolve(url);
        // Square, so the Pokémon keeps its proportions in a square tile.
        const side = Math.max(right - left, bottom - top) + 1;
        const output = document.createElement("canvas");
        output.width = output.height = side;
        output
          .getContext("2d")
          ?.drawImage(
            image,
            left - (side - (right - left + 1)) / 2,
            top - (side - (bottom - top + 1)) / 2,
            side,
            side,
            0,
            0,
            side,
            side,
          );
        resolve(output.toDataURL());
      } catch (error) {
        console.warn("The mascot sprite could not be trimmed", error);
        resolve(url);
      }
    };
    image.onerror = () => {
      console.warn("The mascot sprite could not be loaded", url);
      resolve(url);
    };
    image.src = url;
  });
  trimmed.set(url, result);
  return result;
}

// The mascot sprite, replaced by its cropped version once that is ready.
export function useMascotIcon(sprite: string | undefined): string | undefined {
  const [icon, setIcon] = useState<{ sprite: string; url: string }>();
  useEffect(() => {
    if (!sprite) return;
    let active = true;
    void trim(sprite).then((url) => {
      if (active) setIcon({ sprite, url });
    });
    return () => {
      active = false;
    };
  }, [sprite]);
  return icon && icon.sprite === sprite ? icon.url : sprite;
}

// The browser tab shows the mascot on the same tile as the header: a pale
// tint of the theme color in light mode, the full color in dark mode.
// `theme` names the current theme and color scheme, so the tile is redrawn
// when either changes; effects declared before this one apply them.
export function useFavicon(icon: string | undefined, theme: string) {
  useEffect(() => {
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!icon || !link) return;
    const original = { href: link.href, type: link.type };
    const style = getComputedStyle(document.documentElement);
    const primary = style.getPropertyValue("--primary").trim();
    const card = style.getPropertyValue("--card").trim();
    const dark = document.documentElement.classList.contains("dark");
    const image = new Image();
    // Until the trimmed copy is ready, `icon` is the sprite's own URL; reading
    // it without CORS would taint the canvas.
    image.crossOrigin = "anonymous";
    image.onload = () => {
      const size = 64;
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = size;
      const context = canvas.getContext("2d");
      if (!context) return;
      const tile = new Path2D();
      tile.roundRect(1, 1, size - 2, size - 2, 14);
      context.fillStyle = dark ? primary : card;
      context.fill(tile);
      if (!dark) {
        context.globalAlpha = 0.18;
        context.fillStyle = primary;
        context.fill(tile);
        context.globalAlpha = 0.35;
        context.strokeStyle = primary;
        context.lineWidth = 2;
        context.stroke(tile);
        context.globalAlpha = 1;
      }
      context.imageSmoothingEnabled = false;
      context.drawImage(image, 6, 6, size - 12, size - 12);
      try {
        link.type = "image/png";
        link.href = canvas.toDataURL();
      } catch (error) {
        console.warn("The favicon could not be drawn", error);
      }
    };
    image.src = icon;
    return () => {
      link.href = original.href;
      link.type = original.type;
    };
  }, [icon, theme]);
}
