# Data sources

## Primary ROMs

- Pokémon Sacred Gold complete v1.05: header code `IPKE`, ROM version 0,
  SHA-256 `49f29848878406990ea288f26872d4355c92c4a2677f56973750bbf2566c13c1`.
- Pokémon Storm Silver complete v1.05: header code `IPGE`, ROM version 0,
  SHA-256 `6c1de979abbe1228c6e7d61a770a8e4a761e359e47c1326de7b70a6b18bc3001`.

## Publication model

Sacred Gold and Storm Silver are published as a paired hack family. Both patched
ROMs are parsed independently and compared with their matching USA retail base:

- Sacred Gold against Pokémon HeartGold.
- Storm Silver against Pokémon SoulSilver.

## Coverage and provenance

Each patched ROM produces 505 public Pokémon and battle-form records, 123 public
abilities, 467 playable moves, 513 public items, 142 wild-encounter areas, 737
trainers, and 540 packed map-header locations. The detailed location data includes
1,317 warps, 158 directional connections, 390 trainer-object links, 271 visible
items, and 241 hidden items per hack. Both versions are extracted independently
before their records are merged and compared with the corresponding retail data.

PokéDB provides optional reference metadata only. Patched mechanics come from
each hack ROM, and base-game comparisons come from separately parsed retail ROMs.

## Engine notes

Both hacks use the `gen4_hgss` leaf adapter and retain the retail engine formats.
The sections below describe the extraction contract shared with HeartGold and
SoulSilver.

--8<-- "gen4/hgss-data-sources.md"

### Hack-specific behavior

Both patched ROMs contain profile-scoped malformed NARC size declarations. The
parser accepts them only for these exact hash-matched profiles. Their 192-byte wild
records omit two fields present in the 196-byte retail layout; missing
night-fishing and fishing-swarm replacements remain unavailable rather than being
copied from retail.

Trainer 229 stores form bits `1` on Pinsir even though Pinsir has no Generation IV
form. The raw value remains available for audit, while public references resolve to
base Pinsir instead of inventing a form.

The v1.05 trainer-variant contract verifies that the retail-compatible Silver
selection layout still dispatches all three starter branches. Those exact records
are shown as party tabs. Phone-rematch progression and shared-script location
ownership remain unresolved and are not inferred.
