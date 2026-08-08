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

The profiles identify the exact patched images and inherit the verified HGSS
personal and ability-name locators. Both patched ROMs pass the same 508-record
personal parser as their retail bases, with 286 changed personal records in each
corresponding pair. Their message archives are exactly 788 bytes shorter than the
declared NARC size, so the profiles explicitly allow truncation; ability-name
member 720 is intact and produces all 123 public abilities. No extracted datasets
or comparisons are published on this site yet.
PokéDB will provide optional reference metadata only, never the clean mechanics
baseline; comparisons will come from the separately parsed retail ROMs.

## Engine notes

Both hacks retain their retail game codes. The `gen4_hgss` leaf engine can build
their verified Pokémon and ability slices and the matching clean datasets, but
moves, items, encounters, trainers, locations, and comparative publication still
require fixture-led validation. The paired-hack site therefore remains
non-data-driven and unpublished.
