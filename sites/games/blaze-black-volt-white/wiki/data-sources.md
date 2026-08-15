# Data sources

## Primary ROMs

- Pokémon Blaze Black full v3.1: header code `IRBO`, ROM version 0, SHA-256
  `340c1416b2b107a59c9305c43747761804edce8e876c364abee1f0189bd768ac`.
- Pokémon Volt White full v3.1: header code `IRAO`, ROM version 0, SHA-256
  `232043c9e3f979fff9e1fd67b78d759928e7849b4c2516477b43538fbf7bf851`.

## Publication model

Blaze Black and Volt White are published as one paired hack reference. Both
patched ROMs are parsed independently and merged by stable record identity.
Shared records appear once, while version-specific records retain explicit
Blaze Black and Volt White sections.

Every supported dataset is compared with its exact retail baseline:

- Blaze Black against Pokémon Black (USA), SHA-256
  `b9979189d299a0231d01c8885c0d054b706976ffc75427ca59d84e0ce1493034`.
- Volt White against Pokémon White (USA), SHA-256
  `b288bb061fd646894f5059f55cd0a1efb13b4f0cfd3d9e06e9e42a5bd9431ac6`.

## Coverage and provenance

The wiki derives Pokémon, abilities, items, moves, the type chart, wild
encounters, trainers, and locations directly from the patched ROMs. PokéDB
supplies reference names, descriptions, links, and sprites; it is not used as a
mechanics baseline.

## Engine notes

Both patched images retain all 484 retail filesystem paths. Every configured
NARC retains the retail member count and every fixed-layout record table keeps
its expected record size. The patched content changes personal data,
learnsets, evolutions, moves, items, encounters, trainers, scripts, text, and
NPC trades without replacing the underlying Generation V engine formats.

### Hack-specific record behavior

Two valid engine behaviors appear in these hacks but not in the retail data:
an evolution method can be disabled by clearing only its method ID while stale
operands remain, and a trainer-party archive member can retain inert records
after the party count declared by its trainer header. Extraction follows the
same fields the game uses and ignores those disabled/trailing values.

### Paired-version differences

Blaze Black and Volt White are structurally symmetric. Their ROM-derived
Pokémon, ability, move, trainer, and location datasets match. Twenty-seven
normalized encounter areas differ by version, and three items have
version-specific NPC trade references. Those records render both versions
explicitly. Hack-vs-base comparisons are likewise paired per record, preserving
Blaze Black versus Black and Volt White versus White when their values differ.

The sections below describe the shared Generation V Black/White engine record
formats and decoding techniques.

--8<-- "gen5/bw-data-sources.md"
