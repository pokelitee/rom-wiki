import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import type { Json } from "../../data/types";
import { object } from "../../lib/json";
import { title } from "../../lib/utils";
import { evolutionCondition } from "./evolution";
import { formatName } from "./fields";

export function Evolutions({ value, game }: { value: Json; game: string }) {
  const evolutions = Array.isArray(value) ? value.map(object) : [];
  return (
    <ul className="evolution-list">
      {evolutions.map((evolution, index) => {
        const target = object(evolution.target);
        return (
          <li key={index}>
            <span className="evolution-condition">
              {evolutionCondition(evolution).map((part, partIndex) =>
                typeof part === "string" ? (
                  part
                ) : part.route ? (
                  <Link key={partIndex} to={`/${game}/${part.route}`}>
                    {part.name}
                  </Link>
                ) : (
                  <strong key={partIndex}>{part.name}</strong>
                ),
              )}
            </span>
            <ArrowRight size={15} aria-hidden="true" />
            {typeof target.slug === "string" ? (
              <Link to={`/${game}/pokemon/${target.slug}`}>
                {formatName(String(target.name))}
              </Link>
            ) : (
              <span>{String(target.name ?? "Unknown")}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// Only the stats a Pokémon actually yields; most yield one or two.
export function EvYields({ value }: { value: Json }) {
  const yields = Object.entries(object(value)).filter(
    ([, amount]) => Number(amount) > 0,
  );
  return (
    <p className="badge-list">
      {yields.map(([stat, amount]) => (
        <span className="badge" key={stat}>
          {title(stat)} +{String(amount)}
        </span>
      ))}
    </p>
  );
}
