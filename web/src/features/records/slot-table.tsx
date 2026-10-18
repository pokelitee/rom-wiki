import { Fragment } from "react";
import { EntityLink } from "../../components/entity-link";
import type { DataObject } from "../../data/types";
import { summarizeSlots, type SlotGroup, type SlotSummary } from "./encounter";
import { formatName, tableScroll } from "./fields";

function levels({ minimumLevel, maximumLevel }: SlotSummary): string {
  if (minimumLevel === null || maximumLevel === null)
    return String(minimumLevel ?? maximumLevel ?? "—");
  return minimumLevel === maximumLevel
    ? String(minimumLevel)
    : `${minimumLevel}–${maximumLevel}`;
}

function SlotCells({
  slot,
  game,
  showChance,
}: {
  slot: SlotSummary;
  game: string;
  showChance: boolean;
}) {
  const { pokemon, chance } = slot;
  const name = formatName(String(pokemon.name));
  return (
    <>
      <td>
        {typeof pokemon.slug === "string" ? (
          <EntityLink game={game} route={`pokemon/${pokemon.slug}`}>
            {name}
          </EntityLink>
        ) : (
          name
        )}
      </td>
      <td className="numeric">{levels(slot)}</td>
      {showChance && (
        <td className="numeric">{chance === null ? "—" : `${chance}%`}</td>
      )}
    </>
  );
}

function SlotHead({ showChance }: { showChance: boolean }) {
  return (
    <>
      <th>Pokémon</th>
      <th>Level</th>
      {showChance && <th>Chance</th>}
    </>
  );
}

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
      <table className="detail-table slot-table">
        <thead>
          <tr>
            <SlotHead showChance={showChance} />
          </tr>
        </thead>
        <tbody>
          {summaries.map((slot) => (
            <tr key={String(slot.pokemon.slug ?? slot.pokemon.name)}>
              <SlotCells slot={slot} game={game} showChance={showChance} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Several conditional encounter tables as one, so their columns line up;
// each condition's cell spans its Pokémon.
export function GroupedSlotTable({
  groups,
  game,
}: {
  groups: SlotGroup[];
  game: string;
}) {
  const showChance = groups.some((group) =>
    group.slots.some((slot) => slot.chance !== null),
  );
  const rows = groups.reduce((total, group) => total + group.slots.length, 0);
  return (
    <div className={tableScroll(rows)}>
      <table className="detail-table slot-table grouped-slot-table">
        <thead>
          <tr>
            <th>When</th>
            <SlotHead showChance={showChance} />
          </tr>
        </thead>
        {groups.map((group, index) => (
          <tbody key={index}>
            {group.slots.map((slot, slotIndex) => (
              <tr key={String(slot.pokemon.slug ?? slot.pokemon.name)}>
                {slotIndex === 0 && (
                  <th scope="rowgroup" rowSpan={group.slots.length}>
                    {group.labels.map((label, labelIndex) => (
                      <Fragment key={labelIndex}>
                        {labelIndex > 0 && <br />}
                        <span
                          className={labelIndex ? undefined : "group-label"}
                        >
                          {label}
                        </span>
                      </Fragment>
                    ))}
                  </th>
                )}
                <SlotCells slot={slot} game={game} showChance={showChance} />
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
