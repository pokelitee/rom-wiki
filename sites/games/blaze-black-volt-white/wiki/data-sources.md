# Data sources

The primary inputs are the original full v3.1 releases of Pokémon Blaze Black
and Pokémon Volt White:

- Blaze Black: header code `IRBO`, ROM version 0, SHA-256
  `340c1416b2b107a59c9305c43747761804edce8e876c364abee1f0189bd768ac`.
- Volt White: header code `IRAO`, ROM version 0, SHA-256
  `232043c9e3f979fff9e1fd67b78d759928e7849b4c2516477b43538fbf7bf851`.

The clean USA/Europe NDSi-Enhanced Pokémon Black and White releases are parsed
separately as the exact comparison baselines. PokéDB supplies names,
descriptions, links, and sprites; it is not used as a mechanics baseline.

Both patched images retain all 484 retail filesystem paths. Every configured
NARC retains the retail member count and every fixed-layout record table keeps
its expected record size. The patched content changes personal data,
learnsets, evolutions, moves, items, encounters, trainers, scripts, text, and
NPC trades without replacing the underlying Generation V engine formats.

Two valid engine behaviors appear in these hacks but not in the retail data:
an evolution method can be disabled by clearing only its method ID while stale
operands remain, and a trainer-party archive member can retain inert records
after the party count declared by its trainer header. Extraction follows the
same fields the game uses and ignores those disabled/trailing values.

Blaze Black and Volt White are structurally symmetric. Their ROM-derived
Pokémon, Ability, Move, Trainer, and Location datasets match. Twenty-seven
normalized encounter areas differ by version, and three items have
version-specific NPC trade references. Those records render both versions
explicitly. Hack-vs-base comparisons are likewise paired per record, preserving
Blaze Black versus Black and Volt White versus White when their values differ.

The sections below describe the shared Generation V Black/White engine record
formats and decoding techniques.

--8<-- "gen5-bw-data-sources.md"
