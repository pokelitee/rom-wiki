# ROM Wiki — Code Review Plan

## Context for the reviewing agent

`rom-wiki` is a Python 3.12 tool that parses Pokémon ROM binaries (NDS Gen IV/V
games and hacks), normalizes the extracted data into typed dataclasses, and
renders static MkDocs wikis from it. The repo has an unusually explicit,
documented architecture with strict layering rules — read
`docs/development/architecture.md` in full before reviewing anything. That
document is the primary source of truth for "correct" design in this repo;
treat deviations from its stated rules as review findings, not just generic
style nits.

Also skim `docs/development/data-contracts.md`, `docs/development/frontend.md`,
and `docs/development/adding-a-game.md` for the secondary contracts they
describe.

Toolchain already in place (verify it's actually being honored, don't just
assume): `ruff` (lint + format, see `[tool.ruff.lint]` in `pyproject.toml`),
`mypy` (with a large legacy per-module ignore list — see
`[[tool.mypy.overrides]]`), `pytest` with a large `tests/` tree mirroring
`src/romwiki/`, and GitHub Actions in `.github/workflows/`.

## Review scope

Run against the current diff / branch state unless told otherwise. If asked
for a full-repo audit instead of a diff review, prioritize `src/romwiki/`
over `sites/*/wiki` content and generated archives.

## What to check

### 1. Architectural boundary conformance (repo-specific — highest priority)
- **Layering**: renderers must not read ROM offsets/archive members/script
  opcodes; platform readers must not know Pokémon concepts; engines must not
  import sibling leaf packages (e.g. `gen4/dppt` importing `gen4/hgss`);
  pipeline `enrichment`/`transforms` must dispatch on declared `engine`/format
  fields, not hardcoded generation branches.
- **Registry boundary**: only `platforms/registry.py`, `engines/registry.py`,
  and each engine/platform's own package may name a specific implementation;
  everything else should resolve via `get_platform()` / `get_engine()`.
- **Schema discipline**: normalized fields must be stable/semantic
  (`species_id`, not "byte at offset X"); raw ROM-coordinate data belongs in
  provenance/`source_fields`, not in fields renderers or comparisons consume.
- **No pipeline module reimplementing another layer's job** (e.g. an
  enrichment module doing binary decoding, or a renderer recomputing a stat
  formula instead of consuming a pre-computed schema field).
- Check `tests/engines/test_package_boundaries.py`,
  `tests/renderers/mkdocs/test_package_boundaries.py`,
  `tests/engines/test_contract.py`, and `tests/platforms/test_contract.py` —
  these are the automated guards for the above; confirm new code doesn't
  quietly weaken or route around them.

### 2. Correctness bugs
- Off-by-one / bounds errors in binary parsing (`platforms/nds/*`,
  `engines/**/*.py`) — this is untrusted binary input, wrong bounds can
  silently produce corrupt data rather than crash.
- Incorrect handling of optional/absent ROM fields (the schema explicitly
  distinguishes "mechanic absent" via `features` vs. "record has no entries").
- Cache/fingerprint invalidation logic in `pipeline/build/fingerprint.py`,
  `regeneration.py`, `manifest.py` — check any change to extraction
  dependencies is reflected in fingerprint scope (stale cache = silently wrong
  published data).
- Version-family merge logic (`pipeline/transforms/version_merge.py`) —
  merging must fail loudly on feature-contract mismatches, not silently
  produce an inconsistent site.

### 3. Type safety and mypy gate
- Any new/touched module should be typed cleanly per the project's own stated
  rule ("newly written or touched code should be typed cleanly; shrink the
  ignore list, don't add to it") — flag any addition to the
  `[[tool.mypy.overrides]]` ignore list in `pyproject.toml`.
- Look for `# type: ignore` added without justification, or overly broad
  `Any` usage where a typed contract already exists in `schema/`.

### 4. Test coverage
- Every `src/romwiki/**/foo.py` has a mirrored `tests/**/test_foo.py` — flag
  new source files without a corresponding test file.
- New extraction/enrichment logic should have both a "happy path" test and an
  edge case (missing optional data, malformed/unsupported ROM variant).
- Renderer tests should assert on rendered structure, not just "doesn't
  crash."

### 5. Error handling
- Malformed or unsupported ROM input should fail with a clear, actionable
  error (see `util/errors.py`), not an unguarded exception or a silently
  wrong result.
- No swallowed exceptions (bare `except:`, `except Exception: pass`).
- Profile/contract validation should reject bad config at the boundary
  (per the architecture doc's stated preference), not deep inside extraction.

### 6. Security
- Binary parsing of untrusted/user-supplied ROM files: verify length checks
  before slicing, no unbounded reads driven by attacker-controlled size
  fields, no path traversal via NARC/archive member names when writing output.
- No `eval`/`exec`/`pickle` on untrusted data.
- `sites/server.py` (dev server) — check for path traversal / directory
  escape if it serves files from disk.
- Anything shelling out (`subprocess`, if present) — no unsanitized input into
  a shell command.

### 7. Complexity and maintainability
- `mccabe` max-complexity is set to 20 in `pyproject.toml` — flag functions
  near/over that even if ruff doesn't currently catch them, and flag any
  suspiciously large function added in script/opcode dispatch tables.
- Duplicated logic across `gen4/dppt` and `gen4/hgss`, or `gen5/bw` and
  `gen5/b2w2`, that the architecture doc says should only be promoted to a
  shared module after two independently verified fixtures prove the format is
  shared — flag premature sharing as well as missed legitimate sharing.

### 8. Documentation drift
- `docs/development/architecture.md`, `data-contracts.md`, and
  `adding-a-game.md` should stay accurate to the code. If a change alters a
  layering rule, schema contract, or CLI behavior, check whether the relevant
  doc was updated in the same change.
- `tests/test_documentation.py` — check if it enforces any of this
  automatically and whether it still passes.

### 9. Dependency and CI hygiene
- `pyproject.toml` pins (`ruff==`, `mypy==`) vs. ranges (`mkdocs>=`) — flag
  any new dependency added without a clear reason, or a pin/range choice
  inconsistent with the existing convention.
- `.github/workflows/test.yml` and `deploy-pages.yml` — confirm CI actually
  runs ruff, mypy, and pytest on the changed code path, and that nothing
  bypasses the gate (`continue-on-error`, skipped steps).

### 10. General Python best practices
- Naming, dataclass usage consistent with `schema/` conventions.
- No mutable default arguments, no shared mutable module-level state across
  builds (multiple games/sites are built in one process).
- Deterministic output where the architecture doc promises it (stable
  ordering, deterministic IDs) — flag any use of unordered dict/set iteration
  or non-deterministic sort where output determinism is a stated contract
  (snapshot archives, manifest hashes).

## Output format

For each finding: file path + line number, one-sentence description of the
defect, and which section above it falls under. Rank architecture-boundary
violations and correctness bugs above style/complexity nits. Skip purely
stylistic issues that `ruff format` would already normalize.
