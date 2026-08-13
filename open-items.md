# Open Items

Remaining work for the trainer-relationship effort. Passing tests do not make
partially decoded ROM mechanics complete: every semantic label must come from a
verified engine or profile selector. Names, adjacent IDs, levels, and party
similarity may identify candidates but must never assign a label.

## Scope

The pursued relationship axes are **Starter, Difficulty, Version, and Season**.

`rematch_stage` and `story_stage` are not extended. Coverage already decoded and
verified is kept and still renders — DPPT's Vs. Seeker table (80 families over
232 exact records), BW's Nuvema Town rival rematch, B2W2's Pokémon League
first-clear and rematch records — but no further rematch selector is pursued.
Records whose selector is unknown stay unrelated rather than asserted.

This is a deliberate bound. Rematch selection is expressed differently in every
engine — a table in DPPT, a phone state machine in HGSS, script dispatch for the
Battleground — so chasing it is open-ended per game, while the four pursued axes
are comparatively uniform. It closes the DPPT Gym/Elite Four, HGSS phone-rematch,
and BW rematch-selector items, and removes the only reason to decode HGSS's
script opcode table.

## 1. Open

### B2W2 difficulty level-offset band table

The only open item on a pursued axis, and its value is narrow. The
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
scan. Accepting this as a limitation is reasonable given the payoff.

## 2. Accepted limitations

- **`rematch_stage`** — not pursued; see Scope. Existing verified coverage is
  kept.
- **`story_stage`** — not pursued. Its surface is every story-gated branch in
  every field script rather than one table, so there is no bounded completion
  criterion. DPPT declares it `unresolved`; HGSS, BW, and B2W2 keep `partial`
  because they emit stages from curated lists. All four carry a note.
- **BW roaming Tornadus and Thundurus** — kept explicitly unsupported rather
  than derived from a published offset that points into code.
- **Generation V reference prose** — Pokédex, move, ability, and item
  description banks are not decoded; version-matched PokéDB prose remains the
  documented fallback. Structured mechanics still come from the ROM.
- **DPPT groups with no ROM evidence** — the Spear Pillar partner battle,
  weekend rematch 1, the starter demonstration, and the Pokémon League rival
  rematch have no literal battle command anywhere in the scripts. Previously
  asserted by a hardcoded table, now unpublished.

## 3. Deferred publication validation

Skipped by request as too slow; the trainer work was validated with
`build game --dev` and per-profile extraction instead. Still required before
this effort can close:

1. Regenerate all nine sites and the portal together, without incremental or
   development-page filtering.
2. Confirm stale seasonal encounter routes are removed.
3. Build the combined production artifact.
4. Run the combined site audit and require zero errors.
5. Record generated page count, checked link count, and audit result.
6. Update the deterministic generated-wiki snapshot only after a clean audit.
7. Verify the new snapshot restores successfully.

This matters more than it did: Gen V script-reference coverage roughly tripled
for the B2W2 sites (65 → 241, 65 → 287, 123 → 351), DPPT family IDs changed
shape, and several groups are no longer published. None of that has been checked
at the page level.

The nine sites are Platinum, Renegade Platinum, HeartGold/SoulSilver, Sacred
Gold/Storm Silver, Black/White, Blaze Black/Volt White, Black 2/White 2, Blaze
Black 2/Volt White 2, and Blaze Black 2 Redux/Volt White 2 Redux.

Snapshot generation is not deployment.

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
