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

Four anchored approaches failed; none should be repeated without a new idea:

1. Unanchored byte search over arm9 plus 344 overlays (4.3 MB) for a
   level-indexed ramp or `(threshold, offset)` pairs. Returns only noise.
2. Searching for a Gym difficulty dispatch table. Challenge IDs are consecutive
   (`764`–`771`) while Normal IDs are not (`156,157,154,153,158,155,159,160`),
   so the Normal order should be data — but that sequence appears nowhere as u16
   or u32, in either order, and neither do the League IDs or interleaved pairs.
3. Following the Challenge IDs at `arm9+0x8D4B6`. They sit in a long mixed list
   of trainer and non-trainer IDs with no clean bounds and no pointer resolving
   to a plausible start.
4. Tracing forward from the decoded `GameGetDifficulty` field-script opcode
   (`0x2AF`) to its native VM handler, intending to then find that handler's
   other callers in the battle-engine overlay. Stalls at the same
   missing-anchor problem one level deeper: the VM dispatch table's own
   location and the battle-engine overlay hosting the actual level-adjustment
   code are both unknown, and finding them requires full-binary
   cross-reference analysis (function-boundary detection plus a call-graph
   search across all overlays) that isn't tractable with byte-pattern
   scanning alone. No public source documents a byte offset either — checked
   Ajarmar/universal-pokemon-randomizer-zx's `Gen5RomHandler.java`, which
   only needs `getEliteFourTrainers(isChallengeMode)` to swap trainer
   indices and never touches this runtime level-adjustment code path, so it
   was never reverse-engineered there either. A future attempt likely needs
   proper disassembly tooling with auto-analysis (e.g. Ghidra) rather than ad
   hoc capstone scanning.

The missing anchor is the code that applies the adjustment, reachable from the
save-data difficulty flag or from trainer-party load rather than another data
scan. Leave it unresolved until one of those routines provides a code anchor;
the known party records and runtime behavior are already documented.

### Runtime trainer selectors

- **DPPT partner and special rival battles** — the Spear Pillar partner battle,
  weekend rematch 1, starter demonstration, Pokémon League rival rematch, and
  Dawn/Lucas partner variants have no literal trainer target under the complete
  field-script scan. Their runtime trainer-variable producer is not decoded.
  A real, previously-unwired opcode family was found: `scr_seq.narc` member
  1114 (a shared common handler, not owned by any map header) uses
  `GetApproachingTrainerType` (0xB8), `StartApproachingTrainerTask` (0xB6),
  `GetApproachingTrainerID` (0xB9, `slot, out_var`), and
  `CheckIsApproachingTrainerTaskDone` (0xB7) — all already byte-verified in
  `script_opcode_table.py` but never previously wired into any decoder. Its
  double-battle branch calls `GetApproachingTrainerID(0, ...)` and
  `GetApproachingTrainerID(1, ...)` directly into a two-trainer
  `StartTrainerBattle`'s operands, exactly the shape of the Dawn/Lucas
  partner double battle; the same handler also serves single-trainer
  approaching battles. The remaining blocker: `GetApproachingTrainerID`'s
  value is written by native ARM9 code from overworld NPC-approach state, not
  by another script-visible literal in this file — that native routine
  (analogous to how `gen5/bw/overworld.py` resolves sight-triggered trainer
  IDs from the NPC record's own `scriptUsed` field) is the real next anchor.
  Two other flagged variable-operand sites (script members 400 and 454) were
  checked with the same forward-reachability walk `script_items.py` already
  uses for common-script item grants — a genuine negative result: none of
  the ~40 literal writes later in the same function actually reach the
  flagged call site without an intervening rewrite.
- **HGSS phone rematches** — the phone state machine/table is not decoded. The
  starter-selected Silver branches are decoded independently across the script
  archive. A real, curated phone-contact-ID space was found and verified:
  scanning HeartGold's script archive for `GetPhoneBookRematch`(0x8E)/
  `CheckRegisteredPhoneNumber`(0x93) finds a small set of contact IDs
  (`{17,18,26-39,50}`, ~23 distinct values) clearly separate from the ~900-
  entry raw trainer-ID space, consistently paired with one shared scratch
  variable (`16385` in 32 of the hits) — the same "fixed scratch var"
  convention used elsewhere in this codebase. Tracing the native handler for
  `RunPhoneCall`(0x1AF) through the already-documented command dispatch
  table reached a real function chain (`arm9+0x020470F4` →
  `0x0203EA84` → `0x0203EA34` → `0x0203DFB4`, allocating a 44-byte heap
  struct and copying a 16-byte literal-pool template) three calls deep into
  unlabeled ARM9 code with no public decompilation to cross-check against —
  unlike the already-resolved static-encounter/mart work, there's no
  `pret/pokeheartgold`-equivalent reference for this specific subsystem, so
  asserting a struct-field or table-address guess past that point would
  violate this project's decode-don't-guess bar. The contact→trainer mapping
  itself was not reached.
- **BW non-starter runtime dispatch** — starter-selected Cheren/Bianca families
  are decoded from branches. A complete scan of Black (US)'s field-script
  archive (969 members) for `CallTrainerBattle`/`CallTrainerMultiBattle`
  sites with a variable operand, using the control-flow-aware disassembler to
  confirm reachability (not raw byte matches), found exactly 7 real,
  reachable sites beyond the already-decoded 131 literal ones (members 0,
  104, 863×4, 896). For all 7, every instruction that could reach the
  trainer-ID variable was traced (including called subroutines): the
  variable is always initialized to a literal `0` via `WorkSetConst`
  shortly before the call (member 0's is actually a `PokeDexIsComplete`
  result, not a trainer ID at all), and no other write to that exact
  variable exists anywhere in the statically reachable instruction set.
  Member 896 shows a repeated 5-way `WorkSet(32768, N)` dispatch shape
  (N=0..4, each followed by a shared subroutine call) strongly resembling a
  phone/rematch-style menu, but with no way to verify a name without
  guessing. Conclusion: the real producer is set by ARM9-native engine code
  (a menu selection, save-state read, or similar) before the script runs —
  the same category of problem as the B2W2 difficulty band table above, not
  a script-scanning problem. No further script-side work will move this;
  the next attempt needs an ARM9 code anchor.
- **B2W2 story dispatch** — verified contract families are published, but the
  complete script selector that would replace the contract lists is not
  decoded. The three known rival-battle script sites (Aspertia member 854,
  Floccesy Ranch member 890, Castelia Sewers member 990) were re-located and
  confirmed byte-real in Black 2 (US). BW's generic starter-branch VM idiom
  (`STACK_PUSH, STACK_PUSH_CONST, STACK_CMP(equal), VM_JUMP_IF,
  CallTrainerBattle`) was ported against these same B2W2 sites — despite the
  two engines sharing identical low VM opcode numbers, it finds zero
  matches, even at sites already known to be starter-gated. Disassembling
  member 854 with this codebase's own function-table-driven control-flow
  walker found why: its 33-entry function table's reachable control-flow
  graphs never include offset 2986, where the trainer-battle call physically
  sits — the nearest preceding function legitimately ends at `VMHalt`
  (offset 2840) well before it. Guessing alternate disassembly entry points
  between 2842 and 2986 produced only garbage (bytecode isn't
  self-synchronizing), so that avenue was abandoned rather than pursued
  further. Conclusion: the blocker is disassembler reachability, not
  selector logic — B2W2 script files apparently reference secondary entry
  points outside the primary function table, which is a gap in
  `parse_function_offsets`/the disassembler itself, not just this feature.
  The currently-published, hand-verified `_RIVAL_GROUPS` list remains
  accurate and untouched.

These are worthwhile only when work begins from a new code anchor: the producer
of the trainer variable or state-table lookup. Repeating name/ID clustering or
unanchored byte scans cannot improve confidence.

## 2. Not currently recoverable as structured ROM facts

- **HGSS static encounters (`WildBattle`) — resolved.** A ground-truth field-script
  opcode table (`gen4/hgss/script_opcode_table.py`, sourced from
  pret/pokeheartgold's real decompilation, cross-checked against every opcode
  this codebase had already independently verified, including a direct
  real-ROM byte comparison) replaced the abandoned 90.8%-accurate inferred
  walker. Literal `WildBattle` sites, validated by a real follow-on
  `CheckBattleWon` (directly, or after `ClearFlag`), are now decoded and
  published per map header (`gen4/hgss/scripts.py`'s
  `parse_static_encounter_commands`, wired into
  `pipeline/extraction/locations/arm9_encounter_map.py`). Verified end to end
  against real HeartGold/SoulSilver and Sacred Gold/Storm Silver ROMs: every
  hit is a known, named legendary or gift encounter at its correct real map
  location (Mewtwo/Cerulean Cave, the three legendary birds, Suicune, both
  Snorlax roadblocks, both Sudowoodo blocks, the Lake of Rage red Gyarados,
  the three self-destructing Team Rocket Electrode, the Kyogre/Groudon/
  Rayquaza trio for HGSS; plus Sacred Gold/Storm Silver's own documented
  legendary/gift additions -- Regigigas, Celebi, Mew, Jirachi, Arceus,
  roaming Latios/Latias, and route-guardian Pokémon).
- **HGSS gifts and eggs (`GiveMon`/`GiveEgg`/`GiveTogepiEgg`) — resolved.**
  The missing acceptance signal was reachability, not a `CheckBattleWon`-style
  follow-on: `gen4/hgss/gifts.py` now walks every real function offset with
  the control-flow-aware disassembler (`disassemble_function`, HGSS's own
  opcode table) instead of a raw byte scan, then applies the existing
  species/level bounds check only to instructions actually reached from real
  code. Verified directly against all four real gen4_hgss ROMs (HeartGold,
  SoulSilver, Sacred Gold, Storm Silver): an unfiltered reachable-instruction
  scan alone still surfaces `GiveMon` sites whose species operand is a script
  variable (>= 0x8000, e.g. weekly event prizes), which the bounds check
  correctly rejects; every hit that passes both checks is real and
  independently recognizable (HeartGold/SoulSilver's known Tyrogue/Dratini/
  Dialga-Palkia-Giratina/Eevee/Tentacool gifts, plus Sacred Gold/Storm
  Silver's own hack-added roster). `GiveEgg` sites are additionally
  corroborated by a `BufferSpeciesName` call immediately preceding each one,
  buffering the identical species into the on-screen message -- the same
  validating role `CheckBattleWon` plays for `WildBattle`. `GiveTogepiEgg`
  carries no species operand at all; its species identity rests on the
  opcode's own pret/pokeheartgold-derived name (the same trust already
  extended to every other opcode in this table), resolved dynamically against
  the current profile's own decoded Pokémon name table rather than a
  hardcoded ID, and omitted if that table has no exact "TOGEPI" entry. All
  three are now published as `LocationPokemonGift` records (`kind: "pokemon"`
  or `"egg"`) from `pipeline/extraction/locations/arm9_encounter_map.py`.
  Common-script-routed gifts and other variable-produced operands remain
  unresolved -- this closes the literal-operand and zero-operand cases only.
- **HGSS specialty-shop placement (map attachment) — resolved for dispatch,
  still open for inventory content.** The field-script decoder
  (`gen4/hgss/script_opcode_table.py`) found `MartBuy`/`SpecialMartBuy`/
  `DecorationMart`/`SealMart` as real, named, correctly-widthed opcodes
  (0x113-0x116). Scanning for them (`gen4/hgss/marts.py`'s
  `parse_mart_dispatch_commands`) found 65 real dispatch sites, every one
  cross-referencing to a real, correctly-named map header (Goldenrod City,
  Celadon City's four separate department-store-floor scripts, Pokéathlon
  Dome, Olivine City, Route 32/40, Pokémon League, Battle Frontier). This
  location fact is now published as `LocationMartReference` (kind, raw
  inventory selector, map header) on encounter-map locations.
  What remains genuinely unresolved: the inventory *content* those dispatch
  commands reference. DPPT's two structures for this (an ARM9 pointer table
  of `0xFFFF`-terminated item lists for specialty/decoration/seal marts, and
  a single badge-tiered `(item_id, tier)` list terminated by `(0, 0)` for
  common marts) were searched for exhaustively and mechanically across
  HGSS's entire ARM9 binary and all 129 ARM9 overlays -- zero candidate
  matches of either structure at any length. This is a real negative
  result, not an incomplete search: HGSS encodes mart inventory content
  differently from DPPT (or somewhere this search didn't cover), and no
  further guessing was attempted, consistent with this project's
  decode-don't-guess bar. Do not map inventories from shop or location
  names.

  This dispatch-command gap is distinct from `gen4/hgss/marts.py`'s separate,
  already-published `parse_shop_catalog` (27 standalone, unlocated specialty
  shops with real decoded item lists, gated by `shop_catalog_locator`) — the
  two mechanisms are not currently linked to each other, so a shop catalog
  entry cannot yet be attributed to a specific dispatch command's map header.
  `parse_shop_catalog`'s own shop-name/main-game labels were independently
  re-verified while investigating this item: they trace to
  Ajarmar/universal-pokemon-randomizer-zx's HGSS-specific `hgssShopNames`
  (`Gen4Constants.java`, distinct from that file's separate Platinum array),
  and every published (non-skipped) entry checks out against real HGSS
  geography and story-gating — see `gen4/hgss/marts.py`'s own comment for the
  full verification. This was a documentation gap, not a data error; the
  code and site docs now cite the source.

- **BW roaming Tornadus and Thundurus (species identity) — resolved.** The
  published community offset (`GetRoamerFlagOffsetStartOffset=0x95C4`,
  overlay 10) pointed into code, not data, so it was correctly rejected as a
  guess. What that code actually does was decoded by hand instead: a small
  routine at overlay 10 file offset `0x95C4` (verified byte-identical between
  Black (US) and White (US)) takes a species ID in `r0` and returns which
  roamer it is:

  ```text
  +0x00  LDR  r1, [PC, #0x14]   ; r1 = literal pool word at +0x18 = 0x281
  +0x02  CMP  r0, r1
  +0x04  BEQ  +0x10             ; -> MOV r0, #1 ("Tornadus") ; BX LR
  +0x06  ADD  r1, r1, #1        ; r1 = 0x282 (Tornadus id + 1)
  +0x08  CMP  r0, r1
  +0x0A  BNE  +0x0C             ; -> MOV r0, #2 (default) ; BX LR
  +0x0C  MOV  r0, #0            ; ("Thundurus") ; BX LR
  +0x18  .word 0x00000281       ; literal pool: 641 (Tornadus's real
                                   National Dex number)
  ```

  This exactly matches the (independently written) code comment in
  Ajarmar/universal-pokemon-randomizer-zx's
  `Gen5RomHandler.applyBlackWhiteRoamerPatch` describing the routine's real
  behavior ("returns 0 for Thundurus, 1 for Tornadus, and 2 for any other
  species... computing Thundurus's ID as TornadusID + 1") — confirming both
  the derivation above and that the tool's own patch never needed to guess
  either ID; it only needed to short-circuit the "any other species" branch.
  Tornadus = species 641 (a literal pool constant), Thundurus = species 642
  (computed as Tornadus + 1 by the routine itself) — both correct, real
  National Dex numbers, cross-checked against real-world knowledge, not read
  from the tool's output.

  What remains open is not the species identity but *where this belongs in
  the schema*: Gen5's roaming mechanic has no location-tied activation script
  the way DPPT's `roaming_activations` does (that field is populated from a
  specific NPC/trigger script owning a map header; this routine is a generic
  species-identity helper with no map-header ownership to attach to).
  Publishing this fact needs a deliberate schema decision (e.g. a
  location-less "roaming species" fact rather than a per-map record), not
  more binary parsing.
- **Generation V location section labels** — decoded map headers provide a
  broad display name and stable header identity, but no floor/room label. Warps
  already carry `destination_section_name` when an explicit profile mapping is
  available; no verified BW/B2W2 mapping is currently configured, so the
  renderer shows the section as unavailable rather than deriving one from map
  IDs or duplicate names. This is sharper than "needs a reviewed source": no
  profile in this repository uses the `location_sections` mechanism at all
  yet, and Generation V's 48-byte map-header record (`parse_map_header_table`)
  has no field capable of representing sub-location identity in the first
  place -- it stores `name_index` (the same display name already published),
  `script_file`, `text_file`, `wild_set`, `overworld_file_id`, and
  `matrix_id`, with no floor index or internal-name string. This is a real
  structural difference from Generation IV, whose ROM stores actual internal
  map-name strings (e.g. `MT_CORONET_B1F`) a profile-configured label can be
  corroborated against; Generation V has no ROM-native signal at all to check
  a candidate label against. A checked external source
  (Ajarmar/universal-pokemon-randomizer-zx's `Gen5Constants.java`) has no
  header-ID-keyed name table either -- its only area-indexed array maps a
  different index space (wild-encounter habitat groups) to species lists,
  with location names only as unverified inline comments. Any label entered
  today would be a bare external-name-to-numeric-ID mapping with zero
  independent verification, exactly what `adding-a-game.md` prohibits.
  Completing this needs either a reliable header-ID-keyed source that doesn't
  currently exist, or a different verification strategy entirely -- not more
  binary parsing, and not a data-entry pass against the current mechanism.

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

## Appendix: bounded Generation V (and IV) script awards

Reachable `ItemAdd` commands are published when item ID and quantity are
literal validated operands. Dedicated script ownership comes directly from map
headers; common-script ownership comes from verified NPC/furniture callers, and
all callers are retained.

Work-variable-driven grants are no longer categorically skipped: a second,
control-flow-aware convention is now decoded too, where the item/quantity are
staged into two known scratch registers before a shared give-item call
(`RTCallGlobal` for Generation V, `CallCommonScript` for Generation IV). Only
target IDs independently confirmed against a real, doc-matched item grant are
accepted, since the opcode itself is a general-purpose call reused by many
unrelated global routines — widening it to every call of that opcode produces
mass false positives (verified: pulls in dozens of unrelated common scripts).
Confirmed sets so far: Generation V's Black/White and Black 2/White 2 engines
share `RTCallGlobal` targets `2805`, `2806`, `2807`, and `2814`; Generation IV's
Platinum-based engine uses `CallCommonScript` targets `2016` and `2044`;
HeartGold/SoulSilver's engine uses its own independently-assigned `2033`
(confirmed distinct — Platinum and HeartGold/SoulSilver do not share one ARM9
codebase, so a target ID confirmed for one is never assumed to carry over to
the other). Grants that resolve their item/quantity through some other,
unconfirmed mechanism remain unavailable. The current extractor therefore adds
exact script facts without claiming a complete NPC-gift or item-obtainability
guide — known real gaps remain:

- A still-unidentified vanilla Generation V mechanism behind a handful of
  items at Route 7 and elsewhere. Not yet attempted.
- A still-unlinked Sacred Gold/Storm Silver held-item dispatch table for its
  own hack-added items. A bounded first check (ARM9 diff between Sacred Gold
  and unmodified HeartGold) found only 212 byte differences across 1.12 MB
  of ARM9, meaning any added held-item table is almost certainly in an
  overlay, not ARM9 code. No unanchored full-overlay byte scan was attempted
  for it — this project's own precedent (the B2W2 difficulty band table
  above) already shows that kind of scan without a code anchor doesn't pay
  off, and no anchor exists here yet.

## Appendix: HGSS script decoding

Retained because it is hard-won, not because it is scheduled. It is no longer
needed for starter branches — those turned out to require only one opcode, not
the whole table — but it is the groundwork for any future attempt at HGSS's
script-only trainer-battle locations.

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
- **HGSS's battle command resisted this byte-scanning approach specifically —
  not proof the command itself was unreachable.** Over 166,313 aligned HGSS
  command positions, no opcode had the right shape via this technique: the
  highest distinct operand counts were ~50 across 3,000–4,000 occurrences,
  while opcodes at 100% "operand is a valid trainer" had as few as two
  distinct values and were therefore flags.

**Resolved since, by a different route, not this walker:** cross-referencing
against the already-decoded sight-triggered trainer set (not a byte scan)
found HGSS's talk-triggered battle opcode directly — `0x00D5`, distinct from
Platinum's `0x00E5` (see `gen4/hgss/scripts.py`'s own derivation and
`gen4/hgss/__init__.py`'s two-independent-methods note). This is now decoded
and published (see the HGSS site doc's own Trainers section). The
script-walker/handler-fingerprinting groundwork above remains unused for this
purpose and is retained only in case a future need for a general HGSS
instruction decoder (e.g. HGSS specialty-shop map placement, still open
above) revives it.
