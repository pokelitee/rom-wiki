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
- **HGSS's opening (New Bark Town/Elm's Lab) rival battle** — trainer records
  2, 3, and 265 (solo Cyndaquil/Totodile/Chikorita parties, the type-counter
  to whichever starter the player picks — the same relationship Platinum's
  Route 201 battle uses) appear in no `battle_families` entry at all, and
  have both `locations` and `script_references` empty, unlike every other
  Silver battle (compare `starter-branch-0866-0`'s Azalea Town family, whose
  three trainer IDs do carry a real header). Platinum's structurally
  identical gap (its own opening battle) turned out to be gated behind a
  `GetPlayerGender` check ahead of the starter branch, feeding the trainer ID
  into `StartTagBattle` through a script variable instead of a literal
  operand (see `gen4/platinum/tag_battles.py`'s `_parse_gender_gated_target`).
  That exact mechanism was checked and ruled out here: HGSS's entire script
  archive has only 4 variable-operand `TrainerBattle` (0xD5) sites in total,
  and all 4 belong to one shared `GetEyeTrainerNum`-based overworld
  patrol/rematch handler (script member 953) unrelated to Silver or the
  starter choice. A literal-operand scan for `TrainerBattle(2, ...)`,
  `TrainerBattle(3, ...)`, and `TrainerBattle(265, ...)` across every script
  file also found zero real matches (one coincidental raw-byte hit on an
  unrelated, unnamed opcode does not validate as a battle command). The
  trigger is therefore neither a literal nor a script-variable-fed
  `TrainerBattle` call anywhere in the field-script archive — the same
  category of blocker as the DPPT partner battles and HGSS phone rematches
  below (a native ARM9 code anchor, not a script-scanning gap). Not
  attempted further without one.
- **HGSS phone rematches** — the phone state machine/table is not decoded. The
  starter-selected Silver branches other than the opening battle above (see
  its own bullet) are decoded independently across the script archive. A
  real, curated phone-contact-ID space was found and verified:
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

- **HGSS specialty-shop inventory content.** Shop dispatch is decoded: 65
  `MartBuy`/`SpecialMartBuy`/`DecorationMart`/`SealMart` sites are published as
  `LocationMartReference` records on their map headers. The inventories those
  commands reference are not. DPPT's two inventory structures (an ARM9 pointer
  table of `0xFFFF`-terminated item lists, and a badge-tiered `(item_id, tier)`
  list) were searched for across HGSS's ARM9 binary and all 129 overlays with
  zero matches, so HGSS encodes them differently. The separately published
  `parse_shop_catalog` shops (27 unlocated specialty shops) are not yet linked
  to dispatch sites. Do not map inventories from shop or location names.
- **BW roaming Tornadus and Thundurus.** Their species identity is decoded from
  the routine at overlay 10 offset `0x95C4` (Tornadus is the literal 641,
  Thundurus is computed as 642). Generation V roaming has no location-owned
  activation script, so publishing it needs a schema decision (for example a
  location-less roaming-species fact), not more binary parsing.
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

## 3. Generation III

- **Starter-selected rival parties.** The rival's three parties per battle
  aren't grouped into battle families yet; rematch families are.
- **Rival name.** Trainer records store the ROM's default rival name ("Terry"
  on FireRed/LeafGreen); the player-chosen name lives in save data.
- **Battle Point costs.** Emerald's 20 Battle Frontier tutors are published
  without their BP costs.
- **Compound names.** All-caps ROM names are recased per word, so names that
  later games write with an inner capital read as one word ("Thunderpunch").
- **Emerald systems.** Battle Frontier facilities, contests, and Berry
  mechanics are not decoded.
- **Unused trainer slots** are published as stored, by decision: about 100
  FireRed/LeafGreen slots share one placeholder party, as do about 175 on
  Platinum. Nothing is hidden by inference.

## 4. Release validation

Routine development uses the Python suite and focused data generation. Before preparing a complete React publication:

1. Regenerate every published game's datasets and comparisons without reuse when inputs changed.
2. Export the frontend with `romwiki site export-web` and build the production application.
3. Run browser checks across every published game, section, guide, and download. Verify typed encounter routes, seasons, trainer families, sibling versions, and exact comparisons.
4. Check desktop/mobile layouts, keyboard navigation, light/dark themes, failed requests, direct hash links, and a plain static host under `/rom-wiki/`.
5. Publish the snapshot with `romwiki site snapshot-web`, then verify restoration and every checksum in a clean directory.
6. Commit the pinned manifest through a PR. Merging to `main` deploys the site automatically.

`romwiki site list --published` lists the published wikis.
