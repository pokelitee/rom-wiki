import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Download,
  Gamepad2,
  Library,
  Sparkles,
  Trash2,
} from "lucide-react";
import type { Game } from "../../data/types";
import { Button } from "../../components/ui/button";
import { exportWiki, removeWiki } from "../../generate/library";
import { saveBlob } from "../../lib/download";

export function Portal({
  games,
  onLibraryChange,
}: {
  games: Game[];
  onLibraryChange: () => Promise<void>;
}) {
  const published = games.filter((game) => !game.local);
  const local = games.filter((game) => game.local);
  const generations = [...new Set(published.map((game) => game.generation))];
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
            {published.length} game wikis
          </span>
          <span>
            <BookOpen size={14} />
            Sources included
          </span>
          <Link to="/make">
            <Sparkles size={14} />
            Make a wiki from your ROM
          </Link>
        </div>
      </section>
      {local.length > 0 && (
        <section className="generation-section">
          <div className="generation-heading">
            <h2>Your wikis</h2>
            <span>Made in this browser</span>
          </div>
          <div className="game-grid">
            {local.map((game) => (
              <div className="local-game" key={game.id}>
                <GameCard game={game} />
                <LocalActions game={game} onLibraryChange={onLibraryChange} />
              </div>
            ))}
          </div>
        </section>
      )}
      {generations.map((generation) => (
        <section className="generation-section" key={generation}>
          <div className="generation-heading">
            <h2>Generation {generation}</h2>
            <span>{generation === 3 ? "Game Boy Advance" : "Nintendo DS"}</span>
          </div>
          <div className="game-grid">
            {published
              .filter((game) => game.generation === generation)
              .map((game) => (
                <GameCard game={game} key={game.id} />
              ))}
          </div>
        </section>
      ))}
    </>
  );
}

function GameCard({ game }: { game: Game }) {
  return (
    <Link className="game-card" data-theme={game.theme} to={`/${game.id}`}>
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
      {game.local && (
        <p className="local-badges">
          {!game.local.verified && <span className="badge">Unverified</span>}
          {game.local.outdated && (
            <span className="badge">Made with an earlier generator</span>
          )}
        </p>
      )}
      <span className="game-card-meta">
        {Object.keys(game.sections).length} data sections{" "}
        <ChevronRight size={13} />
      </span>
    </Link>
  );
}

function LocalActions({
  game,
  onLibraryChange,
}: {
  game: Game;
  onLibraryChange: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const name = game.name.replace("Pokémon ", "");
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="local-actions">
      <Button
        variant="outline"
        size="sm"
        disabled={busy}
        aria-label={`Export ${name}`}
        onClick={() =>
          run(async () => {
            const { blob, name: file } = await exportWiki(game.id);
            saveBlob(blob, file);
          })
        }
      >
        <Download size={14} aria-hidden="true" />
        Export
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={busy}
        aria-label={`Delete ${name}`}
        onClick={() => {
          if (confirm(`Delete ${name} from this browser?`))
            run(async () => {
              await removeWiki(game.id);
              await onLibraryChange();
            });
        }}
      >
        <Trash2 size={14} aria-hidden="true" />
        Delete
      </Button>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
