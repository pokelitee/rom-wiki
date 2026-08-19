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

- **HGSS static encounters, gifts, and eggs** — the ARM9 command dispatch and
  matching handlers prove the operand contracts for `WildBattle`, `GiveMon`, and
  `GiveEgg`, and direct map headers prove ownership of dedicated script members.
  However, scanning for an opcode plus valid literal operands and a plausible
  following opcode does not prove that the bytes begin at a reachable command.
  The existing inferred HGSS walker is only 90.8% accurate against Platinum's
  known battle sites, so these acquisitions remain unpublished. Resume with a
  complete, reachable instruction decoder; then add variable-produced operands,
  common-script callers, and specialized handlers such as `GiveTogepiEgg`.
- **HGSS specialty-shop placement** — the inventory catalog is decoded, but no
  shop is attached to a map. ARM9 dispatch identifies the mart-opening handlers,
  but the short opcode/selector signature also occurs inside operands and data;
  requiring only a valid following halfword produced false dispatch candidates.
  Resume with a reachable HGSS instruction decoder and then join its selector to
  the catalog. Do not map inventories from shop or location names.

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
guide — known real gaps remain (e.g. a still-unidentified vanilla Generation V
mechanism behind a handful of items at Route 7 and elsewhere; a still-unlinked
Sacred Gold/Storm Silver held-item dispatch table for its own hack-added
items).

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
