import { useEffect, useState, type ReactNode } from "react";
import { loadData } from "../data/client";
import { SpriteContext } from "../data/sprite-context";
import type { Game, IndexRecord } from "../data/types";

const SPRITE_SECTIONS = ["pokemon", "items"];
// Seconds to wait before each retry of a failed index.
const RETRY_DELAYS = [1, 2, 4, 8, 16];
const NO_SPRITES: ReadonlyMap<string, string> = new Map();

// Loads the Pokémon and item indexes once per game so any link to those
// records can show its icon. Icons are decoration: pages render without them
// until the indexes arrive. A failed index is retried a few times in the
// background, and again whenever the browser comes back online, so a brief
// outage does not leave the game without icons until a reload.
export function SpriteProvider({
  game,
  children,
}: {
  game: Game;
  children: ReactNode;
}) {
  const [sprites, setSprites] = useState<{
    game: string;
    routes: ReadonlyMap<string, string>;
  }>();
  useEffect(() => {
    let active = true;
    const timers = new Set<number>();
    const pending = new Map<string, () => void>();

    function load(section: string, attempt: number) {
      pending.delete(section);
      loadData<{ records: IndexRecord[] }>(game.sections[section].index).then(
        (index) => {
          if (!active) return;
          setSprites((current) => {
            const routes = new Map(
              current?.game === game.id ? current.routes : [],
            );
            for (const record of index.records)
              if (record.sprite)
                routes.set(`${section}/${record.id}`, record.sprite);
            return { game: game.id, routes };
          });
        },
        (error: unknown) => {
          if (!active) return;
          const delay = RETRY_DELAYS[attempt];
          if (delay === undefined) {
            console.warn(`Record icons for ${section} could not load`, error);
            pending.set(section, () => load(section, 0));
            return;
          }
          const retry = () => {
            window.clearTimeout(timer);
            timers.delete(timer);
            load(section, attempt + 1);
          };
          const timer = window.setTimeout(retry, delay * 1000);
          timers.add(timer);
          pending.set(section, retry);
        },
      );
    }

    const retryNow = () => {
      for (const retry of [...pending.values()]) retry();
    };
    window.addEventListener("online", retryNow);
    for (const section of SPRITE_SECTIONS)
      if (game.sections[section]) load(section, 0);
    return () => {
      active = false;
      window.removeEventListener("online", retryNow);
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [game]);
  return (
    <SpriteContext.Provider
      value={sprites?.game === game.id ? sprites.routes : NO_SPRITES}
    >
      {children}
    </SpriteContext.Provider>
  );
}
