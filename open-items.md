# Open Items

Remaining work for the trainer-relationship decoding effort. Passing tests do
not make partially decoded ROM mechanics complete: every semantic label must
come from a verified engine or profile selector. Names, adjacent IDs, levels,
and party similarity may identify candidates but must never assign a label.

## 1. Blocked on an ARM disassembler

These three share one root cause. Table-shaped selectors can be found by
anchored search and validated against structural invariants; logic-shaped ones
cannot, because there is no ground truth to recognise a correct answer with.

### B2W2 difficulty level-offset band table

The Normal/Challenge differences for the verified dispatch pairs are already
stored in the ROM records — Challenge Gym records carry an extra party member at
identical levels, and League rematch Challenge records are +1 level. The
unresolved band table is a separate *runtime* adjustment, so its practical
effect is a displayed level, not the parties themselves. An unanchored search
over arm9 plus 344 overlays (4.3 MB) returns only noise.

### DPPT starter species list

Needed to make block-level branch resolution safe (see item 3). Two candidate
locations were rejected: `overlay_0104+0x12B32` is a long ascending species list
that merely contains the three starters, and `overlay_0078+0x1BC0` is an ARM
literal pool — treating it as a species table is the exact anti-pattern this
project forbids. No field script contains a literal `GivePokemon` for a starter,
so that decoder cannot supply the set either.

### DPPT Battleground rematches (`853`–`860`)

Absent from the Vs. Seeker table, absent from every overlay as a literal
sequence, and backed by no literal battle command. Genuinely variable-supplied;
needs script data-flow analysis.

## 2. Blocked on an HGSS script decode

HGSS does not share DPPT's script layout: only 494 of 965 script files parse
with the DPPT script-table reader, DPPT's battle opcode `0x00E5` yields 6 sites,
and `TRAINER_SCRIPT_REFERENCE_EXTRACTION` is `False`, so no script scanning
happens at all. Both HGSS items are gated behind decoding its opcode set first.

- Port the starter-branch decoder, removing the hardcoded Silver group table.
- Decode the phone-rematch tables and their state machines. Expect the table to
  be tractable and the surrounding state machine not to be.

## 3. Open, unblocked

### DPPT Survival Area pair (`837`–`839`, `871`–`873`)

Real battles that the decoder declines. The starter branch jumps to the start of
a block staging two battles rather than onto a battle. Resolving whole blocks
was implemented and **rejected**: the starter variable `0x800C` is also the
engine's general-purpose scratch variable, so an unrelated comparison captured a
battle belonging to the fall-through and produced a confident, wrong "Venusaur"
branch, while Renegade Platinum collapsed from five families to zero. Unblocked
by the starter species list above.

### BW rematch selectors

Unscoped. "Decode each additional selector" never names them; needs a survey
before it can be estimated. Inherited behaviour in Blaze Black/Volt White must
be verified before its coverage is described as complete.

### DPPT groups with no ROM evidence

The Spear Pillar partner battle, weekend rematch 1, the starter demonstration,
and the Pokémon League rival rematch have no literal battle command anywhere in
the scripts. They were previously asserted by a hardcoded table and are now
unpublished. If they are real, their selector has not been found.

## 4. Accepted limitations

- **BW roaming Tornadus and Thundurus** — kept explicitly unsupported rather
  than derived from a published offset that points into code.
- **Generation V reference prose** — Pokédex, move, ability, and item
  description banks are not decoded; version-matched PokéDB prose remains the
  documented fallback. Structured mechanics still come from the ROM.
- **`story_stage`** — deliberately not pursued. Its surface is every story-gated
  branch in every field script rather than one table, so there is no bounded
  completion criterion. DPPT declares it `unresolved`; HGSS, BW, and B2W2 keep
  `partial` because they do emit stages from curated lists. All four carry a
  note stating the basis.

## 5. Deferred publication validation

Skipped by request as too slow; the trainer work was validated with
`build game --dev` for Platinum and Renegade Platinum instead. Still required
before this effort can close:

1. Regenerate all nine sites and the portal together, without incremental or
   development-page filtering.
2. Confirm stale seasonal encounter routes are removed.
3. Build the combined production artifact.
4. Run the combined site audit and require zero errors.
5. Record generated page count, checked link count, and audit result.
6. Update the deterministic generated-wiki snapshot only after a clean audit.
7. Verify the new snapshot restores successfully.

The nine sites are Platinum, Renegade Platinum, HeartGold/SoulSilver, Sacred
Gold/Storm Silver, Black/White, Blaze Black/Volt White, Black 2/White 2, Blaze
Black 2/Volt White 2, and Blaze Black 2 Redux/Volt White 2 Redux.

Snapshot generation is not deployment. Do not describe the generated snapshot as
published until the separate deployment workflow completes successfully.

The manual acceptance checks and the final completion report (focused and full
test totals, lint results, generated page and audited link totals, audit error
count, snapshot files changed, every selector still partial or unresolved) all
depend on this step and cannot be produced before it.
