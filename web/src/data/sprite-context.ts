import { createContext, useContext } from "react";

// Sprite URLs by record route ("pokemon/bulbasaur", "items/moon-stone").
export const SpriteContext = createContext<ReadonlyMap<string, string>>(
  new Map(),
);

export function useSprite(route: string | undefined): string | undefined {
  const sprites = useContext(SpriteContext);
  return route ? sprites.get(route) : undefined;
}
