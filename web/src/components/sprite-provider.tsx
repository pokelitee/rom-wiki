import { useEffect, useState, type ReactNode } from "react";
import { loadData } from "../data/client";
import { SpriteContext } from "../data/sprite-context";
import type { Game, IndexRecord } from "../data/types";

const SPRITE_SECTIONS = ["pokemon", "items"];

// Loads the Pokémon and item indexes once per game so any link to those
// records can show its icon. Icons are decoration: pages render without them
// until the indexes arrive, or if they fail to load.
export function SpriteProvider({
  game,
  children,
}: {
  game: Game;
  children: ReactNode;
}) {
  const [sprites, setSprites] = useState<ReadonlyMap<string, string>>(
    () => new Map(),
  );
  useEffect(() => {
    let active = true;
    Promise.all(
      SPRITE_SECTIONS.filter((section) => game.sections[section]).map(
        async (section) => {
          const index = await loadData<{ records: IndexRecord[] }>(
            game.sections[section].index,
          );
          return index.records.flatMap((record) =>
            record.sprite
              ? [[`${section}/${record.id}`, record.sprite] as const]
              : [],
          );
        },
      ),
    )
      .then((entries) => {
        if (active) setSprites(new Map(entries.flat()));
      })
      .catch((error: unknown) => {
        console.warn("Record icons could not load", error);
      });
    return () => {
      active = false;
    };
  }, [game]);
  return (
    <SpriteContext.Provider value={sprites}>{children}</SpriteContext.Provider>
  );
}
