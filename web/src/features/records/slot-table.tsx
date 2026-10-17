import { EntityLink } from "../../components/entity-link";
import type { DataObject } from "../../data/types";
import { summarizeSlots } from "./encounter";
import { formatName, tableScroll } from "./fields";

export function SlotTable({
  rows,
  game,
}: {
  rows: DataObject[];
  game: string;
}) {
  const summaries = summarizeSlots(rows);
  if (!summaries.length) return <span className="muted">No Pokémon</span>;
  const showChance = summaries.some((summary) => summary.chance !== null);
  return (
    <div className={tableScroll(summaries.length)}>
      <table className="detail-table">
        <thead>
          <tr>
            <th>Pokémon</th>
            <th>Level</th>
            {showChance && <th>Chance</th>}
          </tr>
        </thead>
        <tbody>
          {summaries.map(({ pokemon, minimumLevel, maximumLevel, chance }) => {
            const name = formatName(String(pokemon.name));
            return (
              <tr key={String(pokemon.slug ?? pokemon.name)}>
                <td>
                  {typeof pokemon.slug === "string" ? (
                    <EntityLink game={game} route={`pokemon/${pokemon.slug}`}>
                      {name}
                    </EntityLink>
                  ) : (
                    name
                  )}
                </td>
                <td className="numeric">
                  {minimumLevel === maximumLevel
                    ? minimumLevel
                    : `${minimumLevel}–${maximumLevel}`}
                </td>
                {showChance && (
                  <td className="numeric">
                    {chance === null ? "—" : `${chance}%`}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
