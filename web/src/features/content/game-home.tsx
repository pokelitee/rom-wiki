import { Link } from "react-router-dom";
import { BookOpen, ChevronRight, Database } from "lucide-react";
import type { Game } from "../../data/types";
import { title } from "../../lib/utils";
import { Document } from "./document";

export function GameHome({ game }: { game: Game }) {
  return (
    <>
      <p className="eyebrow">Generation {game.generation} · Game reference</p>
      <h1>{game.name}</h1>
      <p className="lead">{game.description}</p>
      <div className="section-grid">
        {Object.entries(game.sections).map(([kind, section]) => (
          <Link
            className="panel section-card"
            key={kind}
            to={`/${game.id}/${kind}`}
          >
            <Database size={19} />
            <strong>{title(kind)}</strong>
            <span>
              {Number(section.metadata.record_count).toLocaleString()} records
            </span>
            <ChevronRight size={16} />
          </Link>
        ))}
      </div>
      <div className="notice">
        <BookOpen size={20} />
        <div>
          <strong>Know your sources</strong>
          <p>
            Coverage varies by game and mechanic.{" "}
            <Link to={`/${game.id}/docs/data-sources`}>
              Read data sources and known limitations.
            </Link>
          </p>
        </div>
      </div>
      <Document game={game} id="index" />
    </>
  );
}
