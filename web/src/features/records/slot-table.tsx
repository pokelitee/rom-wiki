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

interface Columns {
  showLevel: boolean;
  showChance: boolean;
}

// Level and chance columns appear only when some row has a value for them;
// a swarm's Pokémon, for example, store neither.
function columns(slots: SlotSummary[]): Columns {
  return {
    showLevel: slots.some(
      (slot) => slot.minimumLevel !== null || slot.maximumLevel !== null,
    ),
    showChance: slots.some((slot) => slot.chance !== null),
  };
}

function SlotCells({
  slot,
  game,
  showLevel,
  showChance,
}: {
  slot: SlotSummary;
  game: string;
} & Columns) {
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
      {showLevel && <td className="numeric">{levels(slot)}</td>}
      {showChance && (
        <td className="numeric">{chance === null ? "—" : `${chance}%`}</td>
      )}
    </>
  );
}

function SlotHead({ showLevel, showChance }: Columns) {
  return (
    <>
      <th>Pokémon</th>
      {showLevel && <th className="numeric">Level</th>}
      {showChance && <th className="numeric">Chance</th>}
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
  const shown = columns(summaries);
  return (
    <div className={tableScroll(summaries.length)}>
      <table className="detail-table slot-table">
        <thead>
          <tr>
            <SlotHead {...shown} />
          </tr>
        </thead>
        <tbody>
          {summaries.map((slot) => (
            <tr key={String(slot.pokemon.slug ?? slot.pokemon.name)}>
              <SlotCells slot={slot} game={game} {...shown} />
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
  const shown = columns(groups.flatMap((group) => group.slots));
  const rows = groups.reduce((total, group) => total + group.slots.length, 0);
  return (
    <div className={tableScroll(rows)}>
      <table className="detail-table slot-table grouped-slot-table">
        <thead>
          <tr>
            <th>When</th>
            <SlotHead {...shown} />
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
                <SlotCells slot={slot} game={game} {...shown} />
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
