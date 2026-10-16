import { Link } from "react-router-dom";
import type { DataObject } from "../../data/types";
import { object } from "../../lib/json";
import { summarizeSlots } from "./encounter";
import { formatName } from "./fields";

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
    <div className="table-scroll">
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
            const sprite = object(pokemon.sprite).url;
            const name = formatName(String(pokemon.name));
            return (
              <tr key={String(pokemon.slug ?? pokemon.name)}>
                <td>
                  <span className="slot-pokemon">
                    {typeof sprite === "string" && (
                      <img
                        src={sprite}
                        alt=""
                        width={40}
                        height={40}
                        loading="lazy"
                      />
                    )}
                    {typeof pokemon.slug === "string" ? (
                      <Link to={`/${game}/pokemon/${pokemon.slug}`}>
                        {name}
                      </Link>
                    ) : (
                      name
                    )}
                  </span>
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
