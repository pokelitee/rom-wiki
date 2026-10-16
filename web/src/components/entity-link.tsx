import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSprite } from "../data/sprite-context";

// A link to a record, with its icon when the record is a Pokémon or item.
export function EntityLink({
  game,
  route,
  children,
}: {
  game: string;
  route: string;
  children: ReactNode;
}) {
  const sprite = useSprite(route);
  return (
    <Link className="entity-link" to={`/${game}/${route}`}>
      {sprite && (
        <img
          className="entity-icon"
          src={sprite}
          alt=""
          width={32}
          height={32}
          loading="lazy"
        />
      )}
      <span>{children}</span>
    </Link>
  );
}
