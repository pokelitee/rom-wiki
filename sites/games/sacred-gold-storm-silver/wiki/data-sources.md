# Data sources

## Primary ROMs

- Pokémon Sacred Gold complete v1.05: header code `IPKE`, ROM version 0,
  SHA-256 `49f29848878406990ea288f26872d4355c92c4a2677f56973750bbf2566c13c1`.
- Pokémon Storm Silver complete v1.05: header code `IPGE`, ROM version 0,
  SHA-256 `6c1de979abbe1228c6e7d61a770a8e4a761e359e47c1326de7b70a6b18bc3001`.

## Publication model

Sacred Gold and Storm Silver are modeled as a paired hack family. Each patched
ROM will be parsed independently and compared with its matching USA retail base:

- Sacred Gold against Pokémon HeartGold.
- Storm Silver against Pokémon SoulSilver.

## Coverage and provenance

The initial profiles identify the exact patched images and inherit the verified
HGSS core archive map. No extracted datasets or comparisons are published yet.
PokéDB will provide optional reference metadata only, never the clean mechanics
baseline; comparisons will come from the separately parsed retail ROMs.

## Engine notes

Both hacks retain their retail game codes and the verified core HGSS archive
paths, but their changed encounter and trainer records still require fixture-led
validation. They reserve the `gen4_hgss` leaf engine and remain non-data-driven
and unpublished until that adapter can build both patched and clean datasets.
