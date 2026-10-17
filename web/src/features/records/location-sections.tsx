import { EntityLink } from "../../components/entity-link";
import { object } from "../../lib/json";
import type { SectionProps } from "./pokemon-sections";
import { mapContext } from "./same-name";

// Where a map's warps lead: one entry per destination map, since several
// doors often lead to the same building.
export function Warps({ value, game }: SectionProps) {
  const warps = (Array.isArray(value) ? value : []).map(object);
  const destinations = [
    ...new Map(
      warps
        .filter((warp) => typeof warp.destination_header_id === "number")
        .map((warp) => [warp.destination_header_id, warp]),
    ).values(),
  ];
  return (
    <ul className="link-list">
      {destinations.map((warp) => {
        const header = Number(warp.destination_header_id);
        return (
          <li key={header}>
            <EntityLink
              game={game.id}
              route={`locations/header-${String(header).padStart(3, "0")}`}
            >
              {String(warp.destination_name ?? `Map ${header}`)}
            </EntityLink>
            <span className="row-context">
              {mapContext(warp.destination_section_name, header)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
