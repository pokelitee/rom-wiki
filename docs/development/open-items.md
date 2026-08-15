# Open Items

This is the remaining selector-decoding work after the cross-engine coverage
pass. Scope is not limited to one title or a fixed set of axes: starter, story,
partner, rematch, version, season, and difficulty variants are all in scope when
the ROM selector can be proven. Names, adjacent IDs, levels, and party similarity
may identify research candidates but never publish a label.

## 1. Open but bounded

### B2W2 difficulty level-offset band table

The only bounded binary lookup still open, and its value is narrow. The
Normal/Challenge differences for the verified dispatch pairs are already stored
in the ROM records — Challenge Gym records carry an extra party member at
identical levels, and League rematch Challenge records are +1 level. The missing
table is a separate *runtime* adjustment, so it affects a displayed level on an
engine whose level/stat divergence is already documented, not the parties.

Three anchored approaches failed; none should be repeated without a new idea:

1. Unanchored byte search over arm9 plus 344 overlays (4.3 MB) for a
   level-indexed ramp or `(threshold, offset)` pairs. Returns only noise.
2. Searching for a Gym difficulty dispatch table. Challenge IDs are consecutive
   (`764`–`771`) while Normal IDs are not (`156,157,154,153,158,155,159,160`),
   so the Normal order should be data — but that sequence appears nowhere as u16
   or u32, in either order, and neither do the League IDs or interleaved pairs.
3. Following the Challenge IDs at `arm9+0x8D4B6`. They sit in a long mixed list
   of trainer and non-trainer IDs with no clean bounds and no pointer resolving
   to a plausible start.

The missing anchor is the code that applies the adjustment, reachable from the
save-data difficulty flag or from trainer-party load rather than another data
scan. Leave it unresolved until one of those routines provides a code anchor;
the known party records and runtime behavior are already documented.

### Runtime trainer selectors

- **DPPT partner and special rival battles** — the Spear Pillar partner battle,
  weekend rematch 1, starter demonstration, Pokémon League rival rematch, and
  Dawn/Lucas partner variants have no literal trainer target under the complete
  field-script scan. Their runtime trainer-variable producer is not decoded.
- **HGSS phone rematches** — the phone state machine/table is not decoded. The
  starter-selected Silver branches are decoded independently across the script
  archive.
- **BW non-starter runtime dispatch** — starter-selected Cheren/Bianca families
  are decoded from branches. Other trainer-variable producers remain open.
- **B2W2 story dispatch** — verified contract families are published, but the
  complete script selector that would replace the contract lists is not decoded.

These are worthwhile only when work begins from a new code anchor: the producer
of the trainer variable or state-table lookup. Repeating name/ID clustering or
unanchored byte scans cannot improve confidence.

## 2. Not currently recoverable as structured ROM facts

- **HGSS Safari Zone block encounters** — `FieldSystem_GenerateSafariEncounter`
  proves that the runtime loads ten slots by saved area, encounter method, and
  time of day. `safari_zone.c` proves the six-area save layout, placed block
  objects, and per-area age state. The missing anchor is
  `SafariZoneAreaSet_LoadAreaEncounters`: its joins from area, block categories,
  area age, and method to the ROM encounter tables are not yet decompiled into a
  complete layout that can be validated independently in retail and hacks.
- **HGSS static encounters, gifts, and eggs** — the retail decomp proves that
  `ScrCmd_GiveMon` consumes species, level, held item, form, ability, and result
  operands through `ScriptGetVar`, while `ScrCmd_GiveEgg` consumes species and
  gift-location offset. The command-table indices, control-flow-safe HGSS script
  decoder, and ownership of called/common scripts are still missing. Those are
  required before literal operands can be distinguished from variables and data.
- **HGSS specialty-shop placement** — the inventory catalog is decoded, but no
  verified HGSS shop-command index and selector operand contract has been joined
  to each map header's script member. Resume from the command dispatch entry for
  the mart-opening handler; do not map inventories from shop names.

- **BW roaming Tornadus and Thundurus** — kept explicitly unsupported rather
  than derived from a published offset that points into code.
- **Generation V location section labels** — decoded map headers provide a
  broad display name and stable header identity, but no floor/room label. Warps
  already carry `destination_section_name` when an explicit profile mapping is
  available; no verified BW/B2W2 mapping is currently configured, so the
  renderer shows the section as unavailable rather than deriving one from map
  IDs or duplicate names. Completing this requires a reviewed per-header source,
  not more binary parsing.

## 3. Release validation

Routine development uses the full unit suite and focused site generation; it does
not regenerate or snapshot every site after each renderer change. Before the next
snapshot or deployment:

1. Regenerate all nine sites and the portal together, without incremental or
   development-page filtering.
2. Confirm stale seasonal encounter routes are removed.
3. Build the combined production artifact.
4. Run the combined site audit and require zero errors.
5. Record generated page count, checked link count, and audit result.
6. Update the deterministic generated-wiki snapshot only after a clean audit.
7. Verify the new snapshot restores successfully.

Run the combined audit against a clean output directory. A locked pre-existing
artifact, especially the root `404.html` on Windows, can prevent cleanup or audit
reads even when every selected site generated and built successfully.

The nine sites are Platinum, Renegade Platinum, HeartGold/SoulSilver, Sacred
Gold/Storm Silver, Black/White, Blaze Black/Volt White, Black 2/White 2, Blaze
Black 2/Volt White 2, and Blaze Black 2 Redux/Volt White 2 Redux.

Snapshot generation is not deployment.

## Appendix: bounded Generation V script awards

Reachable `ItemAdd` commands are published only when item ID and quantity are
literal validated operands. Dedicated script ownership comes directly from map
headers; common-script ownership comes from verified NPC/furniture callers, and
all callers are retained. Commands using work variables are deliberately skipped
because their producers and repeatability conditions are not yet normalized.
The current extractor therefore adds exact script facts without claiming a
complete NPC-gift or item-obtainability guide.

## Appendix: HGSS script decoding

Retained because it is hard-won, not because it is scheduled. It is no longer
needed for starter branches — those turned out to require only one opcode, not
the whole table — but it is the groundwork for any future attempt at HGSS's
script-only battle locations.

- **Command dispatch tables are located** by scanning for long runs of
  word-aligned pointers into loaded code: Platinum at `arm9+0x0EAC58` (840
  entries), HeartGold at `arm9+0x0FAD00` (853). Validated by Platinum, whose
  command count is independently known to be `0x033A`.
- **Operand readers are identified.** Three per game advance the VM's script
  cursor; Platinum's `0x0203E838` reads 2 bytes and serves 547 handlers, and is
  byte-identical to HeartGold's `0x0203FE2C`.
- **A script walker works, fitted to the scripts rather than the handlers.**
  Learning each command's operand width by which candidate sustains the longest
  chain of valid successors reaches **90.8%** agreement with Platinum's 98 known
  battle sites, against 1% for handler-derived counts.
- **Handler fingerprinting does not work** — only 6 of the 840/853 handlers are
  byte-identical between the games.
- **HGSS's battle command is still unidentified, and alignment is not the
  obstacle.** Over 166,313 aligned HGSS command positions, no opcode has the
  right shape: the highest distinct operand counts are ~50 across 3,000–4,000
  occurrences, while opcodes at 100% "operand is a valid trainer" have as few as
  two distinct values and are therefore flags. Test first whether HGSS invokes
  trainer battles from overworld trainer-sight events rather than from scripts
  with literal IDs, which would explain all of the above and is consistent with
  `TRAINER_SCRIPT_REFERENCE_EXTRACTION` already being `False` for this engine.
