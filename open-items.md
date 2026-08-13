# Open Items

Remaining work for the trainer-relationship decoding effort. Passing tests do
not make partially decoded ROM mechanics complete: every semantic label must
come from a verified engine or profile selector. Names, adjacent IDs, levels,
and party similarity may identify candidates but must never assign a label.

## 1. Blocked without further disassembly

Table-shaped selectors can be found by anchored search and validated against
structural invariants; logic-shaped ones cannot, because there is no ground
truth to recognise a correct answer with. `capstone` is available as a dev
dependency and already resolved the starter accessor, so these are tractable
with effort rather than fundamentally blocked.

### B2W2 difficulty level-offset band table

The Normal/Challenge differences for the verified dispatch pairs are already
stored in the ROM records — Challenge Gym records carry an extra party member at
identical levels, and League rematch Challenge records are +1 level. The
unresolved band table is a separate *runtime* adjustment, so its practical
effect is a displayed level, not the parties themselves.

Three anchored approaches have failed; none should be repeated without a new
idea:

1. Unanchored byte search over arm9 plus 344 overlays (4.3 MB) for a
   level-indexed ramp or `(threshold, offset)` pairs. Returns only noise,
   because there is no ground truth to recognise a correct table with.
2. Searching for a Gym difficulty dispatch table. The Challenge IDs are
   consecutive (`764`–`771`) while the Normal IDs are not
   (`156,157,154,153,158,155,159,160`), so the Normal order should be data —
   but that sequence appears nowhere as u16 or u32, in either order, and
   neither do the League IDs or interleaved `(normal, challenge)` pairs.
3. Following the one hit that did land — the Challenge IDs at `arm9+0x8D4B6`.
   It sits inside a long mixed list of trainer and non-trainer IDs (Leaders,
   Elite Four, Ace Trainers, Subway Bosses) with no clean bounds: constraining
   entries to real trainer IDs truncates it at 66, and relaxing that swallows
   1278 entries spanning several unrelated tables. No pointer resolves to a
   plausible table start.

The missing anchor is the code that applies the adjustment. Finding it needs a
way in from the save-data difficulty flag or from trainer-party load, not
another scan of the data.

### DPPT Battleground rematches (`853`–`860`)

The selector is **identified but not safely generalizable**. Script 156 branches
on variable `0x8004`, comparing it against trainer IDs `853`, `854`, `855`,
`856`, `857` and jumping to a distinct target for each — a "which Leader is here
today" dispatch. The IDs appear as comparison operands, not battle operands,
which is why the battle scan never saw them; the battle itself is invoked from
the variable.

Two reasons this is not published:

- It does not relate a first battle to its rematch. The dispatch chooses between
  *different characters*, so it yields no variant family. Relating `246` to
  `858` would need whatever selects between them, which this is not.
- Generalizing it produces noise. Scanning all scripts for "compare a variable
  against several trainer IDs, then jump" yields 148 groups in Platinum, mostly
  ordinary thresholds and counters (`5`, `6`, `50`, `100`, `150`, `200`, `255`)
  that merely coincide with low trainer IDs. Separating the real dispatch would
  need an arbitrary magnitude threshold, which is heuristic stacking rather than
  decoding.

It could yield location links for these otherwise-unlinked records if a
principled way to distinguish a trainer-ID dispatch from a numeric comparison is
found. Small-integer ambiguity in a large corpus is the recurring obstacle here,
as it is for the HGSS opcode search.

## 2. Blocked on an HGSS script decode

HGSS does not share DPPT's script layout: only 494 of 965 script files parse
with the DPPT script-table reader, DPPT's battle opcode `0x00E5` yields 6 sites,
and `TRAINER_SCRIPT_REFERENCE_EXTRACTION` is `False`, so no script scanning
happens at all. Both HGSS items are gated behind decoding its opcode set first.

- Port the starter-branch decoder, removing the hardcoded Silver group table.
- Decode the phone-rematch tables and their state machines. Expect the table to
  be tractable and the surrounding state machine not to be.

Statistical opcode search does not work here and should not be retried as-is.
Every HGSS trainer record has a party, so "operand is a valid trainer" is barely
stronger than "operand is a small number", and precision ranking returns a dozen
near-tied candidates. The best-looking one, `0x02EF` — 616 sites, 273 distinct
trainer operands, spread across the whole ID range — is **not** the battle
command: its sites split 333/283 across odd and even alignment relative to the
code offset, its second operand is `0xFF` in 542 of 616 cases, and its
"follow-on opcode" histogram descends `0, 1, 2, 3, …`. Those are byte
coincidences inside data, found by scanning unaligned over a large corpus.

Identifying the command requires HGSS's actual script command table, which means
disassembling its script interpreter rather than searching its scripts.

## 3. Open, unblocked

### BW rematch selectors

Now scoped. Surveying same class+name records whose parties strictly escalate
gives 13 candidate groups, 12 of them outside any existing family. The clearest
are the Elite Four pairs `229`/`564`, `230`/`565`, `231`/`566`, then the three
Backers trios, Infielder Alex (`321, 192, 322, 323`) and Ace Trainer Elmer
(`607`/`608`).

Every one of those records is already reachable and linked; what is missing is a
selector *relating* a first battle to its rematch, exactly as for the DPPT Elite
Four. Candidate identification alone must not assign a Rematch label, so none is
published. The follow-on relaxation below linked the remaining rival battles but
did not create any new family.

Inherited behaviour in Blaze Black/Volt White is verified for the link scan
(both ROMs agree exactly) but not yet for any new family.

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
