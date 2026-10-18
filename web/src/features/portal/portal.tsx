import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Gamepad2,
  Library,
} from "lucide-react";
import type { Game } from "../../data/types";

export function Portal({ games }: { games: Game[] }) {
  const generations = [...new Set(games.map((game) => game.generation))];
  return (
    <>
      <section className="portal-hero">
        <div className="pill">
          <span />
          The ROM reference library
        </div>
        <h1>
          Your games.
          <br />
          <em>The exact details.</em>
        </h1>
        <p>
          Explore Pokémon, encounters, trainers, and mechanics decoded from the
          games themselves. Pick a game to get started.
        </p>
        <div className="hero-meta">
          <span>
            <Library size={14} />
            {games.length} game wikis
          </span>
          <span>
            <BookOpen size={14} />
            Sources included
          </span>
        </div>
      </section>
      {generations.map((generation) => (
        <section className="generation-section" key={generation}>
          <div className="generation-heading">
            <h2>Generation {generation}</h2>
            <span>Nintendo DS</span>
          </div>
          <div className="game-grid">
            {games
              .filter((game) => game.generation === generation)
              .map((game) => (
                <Link
                  className="game-card"
                  data-theme={game.theme}
                  key={game.id}
                  to={`/${game.id}`}
                >
                  <span className="game-card-icon">
                    {game.mascot ? (
                      <img
                        src={game.mascot.sprite}
                        alt=""
                        width={64}
                        height={64}
                        loading="lazy"
                      />
                    ) : (
                      <Gamepad2 size={22} />
                    )}
                  </span>
                  <ArrowUpRight className="card-arrow" size={19} />
                  <h3>{game.name.replace("Pokémon ", "")}</h3>
                  <p>{game.description}</p>
                  <span className="game-card-meta">
                    {Object.keys(game.sections).length} data sections{" "}
                    <ChevronRight size={13} />
                  </span>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </>
  );
}
