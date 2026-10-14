# Personal (species) stats archive `a/0/1/6`: national dex species occupy
# members 1-649, member 0 is an unused placeholder record, and members
# 650-667 are 18 alternate-forme/battle-transformation records (Deoxys,
# Wormadam, Giratina, Shaymin, Rotom, Basculin, Castform, Darmanitan,
# Meloetta -- see PERSONAL_FORM_MEMBERS/PERSONAL_TRANSFORMATION_MEMBERS
# below for the exact, verified mapping). Confirmed empirically against a
# real Black ROM: `a/0/1/6` has 669 total archive members; the last (index
# 668) is a 1300-byte table unrelated to personal records and is excluded
# from PERSONAL_RECORD_COUNT.
PERSONAL_RECORD_COUNT = 668

# PersonalInfo5BW.SIZE (PKHeX.Core/PersonalInfo/Info/PersonalInfo5BW.cs);
# confirmed against a real Black ROM record (Bulbasaur, member 1).
PERSONAL_RECORD_SIZE = 0x3C

# Unlike every other member (all a uniform PERSONAL_RECORD_SIZE), the member 0
# "none" placeholder is a distinct, shorter 56-byte record in a real Black
# ROM. Its content is unused (species 0 is never a real Pokémon), so
# `parse_personal_record` zero-pads it rather than rejecting it.
PERSONAL_PLACEHOLDER_MEMBER = 0
PERSONAL_PLACEHOLDER_RECORD_SIZE = 56

PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {0: "none"}

# The 18 forme records (650-667) identified by decoding their real base
# stats/types from a Black ROM and cross-referencing against
# Ajarmar/universal-pokemon-randomizer-zx's Gen5Constants.java, which has an
# authoritative `bw1FormeCount = 18` and confirms Tornadus/Thundurus/
# Landorus-Therian, Kyurem-Black/White, and Keldeo-Resolute are Black
# 2/White 2-only additions (bw2formeOffset = 35) absent from vanilla BW --
# gated behind items/tutors (Reveal Glass, DNA Splicers, Secret Sword tutor)
# that don't exist in this release.
#
# 13 real, independently-obtainable forms, each with its own PokéDB
# reference file under pokedb/.output/gen5/pokemon/variant/ -- same shape as
# gen4_platinum's PERSONAL_FORM_MEMBERS.
PERSONAL_FORM_MEMBERS: dict[int, str] = {
    650: "deoxys-attack",
    651: "deoxys-defense",
    652: "deoxys-speed",
    653: "wormadam-sandy",
    654: "wormadam-trash",
    655: "shaymin-sky",
    656: "giratina-origin",
    657: "rotom-heat",
    658: "rotom-wash",
    659: "rotom-frost",
    660: "rotom-fan",
    661: "rotom-mow",
    665: "basculin-blue-striped",
}

# 5 battle-only transformations (Castform's weather forms, Darmanitan's Zen
# Mode, Meloetta's Pirouette forme): real distinct stats/types decoded from
# the ROM, but no player independently owns/catches one -- they trigger
# mid-battle via weather/ability/move, and PokéAPI categorizes them
# "transformation" rather than a separately obtainable Pokémon, so PokéDB has
# no dedicated reference page for them. `base_slug` must match the base
# record's own PokéDB-derived slug exactly (verified against the real
# PokéDB JSON `name` fields, which differ from the bare species name for
# Darmanitan/Meloetta).
PERSONAL_TRANSFORMATION_MEMBERS: dict[int, dict[str, str]] = {
    662: {"base_slug": "castform", "label": "Sunny Form"},
    663: {"base_slug": "castform", "label": "Rainy Form"},
    664: {"base_slug": "castform", "label": "Snowy Form"},
    666: {"base_slug": "darmanitan-standard", "label": "Zen Mode"},
    667: {"base_slug": "meloetta-aria", "label": "Pirouette Forme"},
}

# Trainer-party form operands that select a battle form with its own
# personal record; slugs match the PERSONAL_FORM_MEMBERS entries above.
# Retail Black uses only Wormadam and Basculin here. Blaze Black/Volt White
# additionally use every Rotom appliance form in trainer parties.
TRAINER_FORM_SLUGS: dict[tuple[int, int], str] = {
    (413, 1): "wormadam-sandy",
    (413, 2): "wormadam-trash",
    (479, 1): "rotom-heat",
    (479, 2): "rotom-wash",
    (479, 3): "rotom-frost",
    (479, 4): "rotom-fan",
    (479, 5): "rotom-mow",
    (550, 1): "basculin-blue-striped",
}

# Shellos and Gastrodon's East Sea forms reuse their base personal records.
# They do not appear in retail Black's trainer parties, but both hacks use
# them with the same Gen V form operand used by the game elsewhere.
TRAINER_COSMETIC_FORM_LABELS: dict[tuple[int, int], str] = {
    (422, 1): "East Sea",
    (423, 1): "East Sea",
}

# Wild slots use the same form operand as trainer parties. Forms backed by a
# public PokéDB record can use its sprite; cosmetic and battle-only forms
# retain the base record and add only their in-game form label.
ENCOUNTER_FORM_SLUGS = dict(TRAINER_FORM_SLUGS)
ENCOUNTER_COSMETIC_FORM_LABELS: dict[tuple[int, int], str] = {
    **TRAINER_COSMETIC_FORM_LABELS,
    (351, 1): "Sunny Form",
    (351, 2): "Rainy Form",
    (351, 3): "Snowy Form",
    (421, 1): "Sunshine Form",
    (555, 1): "Zen Mode",
    **{
        (585, form_id): season
        for form_id, season in enumerate(("Summer", "Autumn", "Winter"), 1)
    },
    **{
        (586, form_id): season
        for form_id, season in enumerate(("Summer", "Autumn", "Winter"), 1)
    },
    (648, 1): "Pirouette Forme",
}

# Name-table entry counts, confirmed empirically by decoding every entry in
# a real Black ROM's `a/0/0/2` (TextStrings) NARC -- see
# `gen5/shared/messages.py`. Each includes a leading placeholder entry
# (index 0) and, for Pokémon, two trailing "Egg" entries (650-651) alongside
# the 649 real species.
ITEM_NAME_COUNT = 627
POKEMON_NAME_COUNT = 652
# The two version-specific Pokédex banks contain the placeholder plus all
# 649 species. Egg labels are names, not Pokédex species.
POKEMON_DESCRIPTION_COUNT = 650
