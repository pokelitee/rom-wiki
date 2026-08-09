# Data sources

## Primary ROMs

- Pokémon Sacred Gold complete v1.05: header code `IPKE`, ROM version 0,
  SHA-256 `49f29848878406990ea288f26872d4355c92c4a2677f56973750bbf2566c13c1`.
- Pokémon Storm Silver complete v1.05: header code `IPGE`, ROM version 0,
  SHA-256 `6c1de979abbe1228c6e7d61a770a8e4a761e359e47c1326de7b70a6b18bc3001`.

## Publication model

Sacred Gold and Storm Silver are modeled as a paired hack family. Each patched
ROM will be parsed independently and compared with its matching USA retail base:

- Sacred Gold against Pokémon HeartGold.
- Storm Silver against Pokémon SoulSilver.

## Coverage and provenance

The profiles identify the exact patched images and inherit the verified HGSS
archive and executable locators. Both patched ROMs produce 508 Pokémon records,
123 public abilities, 471 move records, 513 public items, 142 wild-encounter
areas, 737 trainers, and 540 packed map-header locations. Each dataset is parsed
independently before the sibling versions are merged and compared with their
matching retail bases. The detailed location slice adds 1,317 warps, 158
directional connections, 390 trainer-object links, 271 visible items, and 241
hidden items per hack.

Both hacks contain profile-scoped malformed NARC size declarations. The parser
accepts them only through explicit flags on these exact hash-matched profiles.
Their 192-byte encounter records omit two fields present in the 196-byte retail
record; unavailable night-fishing and fishing-swarm replacements remain absent
rather than being inferred.

Trainer 229 stores form bits `1` on Pinsir in both patched ROMs even though
Pinsir has no Generation IV form. The raw form value is retained for audit, and
the rendered reference resolves to base Pinsir without inventing a new form.
PokéDB will provide optional reference metadata only, never the clean mechanics
baseline; comparisons will come from the separately parsed retail ROMs.

Each patched ROM independently verifies the same 52-record BP move-tutor table,
505 compatibility rows, 11 true NPC trades, 27 supported specialty shops with
141 item entries, and ten Pickup level bands as its matching retail version.
Trade names and species still come from each hack's own patched message and
trade archives; they are not copied from retail.

## Engine notes

Both hacks retain their retail game codes. Formats proven identical to retail
HGSS reuse shared Generation IV parsers; the `gen4_hgss` leaf continues to own
the distinct encounter and packed map-header formats. Learnsets, evolutions,
TM/HM mappings, egg moves, and normalized relationships feed the Pokémon, move,
item, encounter, and trainer pages.

Trainer-class payout multipliers, script-only/shared trainer battles, and
trade/shop locations are not published because their exact HGSS executable or
script semantics remain unverified. Static encounters, gifts and eggs,
Headbutt tree slots, and Safari Zone block configuration likewise remain
explicit blockers: retail offset inventories are not treated as proof of the
patched scripts, and no placeholder hack data is emitted.
