from __future__ import annotations

GEN5_BASE_SPECIES_COUNT = 649

# B2W2's personal archive has members 0-708 followed by a regional-Pokédex
# table at member 709. Members 650-684 are internal Pokéstar Studios actors;
# the ordinary alternate forms therefore begin at 685 rather than BW's 650.
PERSONAL_RECORD_COUNT = 709
PERSONAL_RECORD_SIZE = 0x4C
PERSONAL_INTERNAL_MEMBERS: dict[int, str] = {
    0: "none",
    **{member: f"pokestar-studios-{member - 649}" for member in range(650, 685)},
}

PERSONAL_FORM_MEMBERS: dict[int, str] = {
    685: "deoxys-attack",
    686: "deoxys-defense",
    687: "deoxys-speed",
    688: "wormadam-sandy",
    689: "wormadam-trash",
    690: "shaymin-sky",
    691: "giratina-origin",
    692: "rotom-heat",
    693: "rotom-wash",
    694: "rotom-frost",
    695: "rotom-fan",
    696: "rotom-mow",
    700: "basculin-blue-striped",
    703: "kyurem-white",
    704: "kyurem-black",
    705: "keldeo-resolute",
    706: "tornadus-therian",
    707: "thundurus-therian",
    708: "landorus-therian",
}

PERSONAL_TRANSFORMATION_MEMBERS: dict[int, dict[str, str]] = {
    697: {
        "base_slug": "castform",
        "label": "Sunny Form",
        "slug": "castform-sunny",
    },
    698: {
        "base_slug": "castform",
        "label": "Rainy Form",
        "slug": "castform-rainy",
    },
    699: {
        "base_slug": "castform",
        "label": "Snowy Form",
        "slug": "castform-snowy",
    },
    701: {
        "base_slug": "darmanitan-standard",
        "label": "Zen Mode",
        "slug": "darmanitan-zen",
    },
    702: {
        "base_slug": "meloetta-aria",
        "label": "Pirouette Forme",
        "slug": "meloetta-pirouette",
    },
}

TRAINER_FORM_SLUGS: dict[tuple[int, int], str] = {
    (386, 1): "deoxys-attack",
    (386, 2): "deoxys-defense",
    (386, 3): "deoxys-speed",
    (413, 1): "wormadam-sandy",
    (413, 2): "wormadam-trash",
    (479, 1): "rotom-heat",
    (479, 2): "rotom-wash",
    (479, 3): "rotom-frost",
    (479, 4): "rotom-fan",
    (479, 5): "rotom-mow",
    (487, 1): "giratina-origin",
    (492, 1): "shaymin-sky",
    (550, 1): "basculin-blue-striped",
    (555, 1): "darmanitan-zen",
    (641, 1): "tornadus-therian",
    (642, 1): "thundurus-therian",
    (645, 1): "landorus-therian",
    (646, 1): "kyurem-white",
    (646, 2): "kyurem-black",
    (647, 1): "keldeo-resolute",
}

_UNOWN_FORM_LABELS = (*"BCDEFGHIJKLMNOPQRSTUVWXYZ", "!", "?")

TRAINER_COSMETIC_FORM_LABELS: dict[tuple[int, int], str] = {
    **{
        (201, form_id): label
        for form_id, label in enumerate(_UNOWN_FORM_LABELS, start=1)
    },
    (422, 1): "East Sea",
    (423, 1): "East Sea",
    (618, 5): "Form 5",
}

# Darmanitan's Zen Mode has no independently obtainable PokéDB record, so
# wild encounters label it below while retaining the base-form reference.
ENCOUNTER_FORM_SLUGS = {
    key: slug for key, slug in TRAINER_FORM_SLUGS.items() if key != (555, 1)
}
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

GEN5_MACHINE_COUNT = 101

# B2W2 retains the 649 species names, adds 35 Pokéstar Studios actor names,
# and keeps the placeholder plus two trailing Egg entries.
POKEMON_NAME_COUNT = 687
# The shared Pokédex bank includes the 650 base entries plus forme/actor text.
POKEMON_DESCRIPTION_COUNT = 733
ITEM_NAME_COUNT = 639

GEN5_ITEM_FIELD_USE_NAMES = (
    "none",
    "healing",
    "town-map",
    "explorer-kit",
    "bicycle",
    "journal",
    "tm-hm",
    "mail",
    "berry",
    "poffin-case",
    "pal-pad",
    "poke-radar",
    "sprayduck",
    "mulch",
    "honey",
    "vs-seeker",
    "old-rod",
    "good-rod",
    "super-rod",
    "bag-message",
    "evolution-stone",
    "escape-rope",
    "azure-flute",
    "vs-recorder",
    "gracidea",
    "dowsing-machine",
    "xtransceiver",
    "medal-box",
    "dna-splicers-fuse",
    "dna-splicers-separate",
    "reveal-glass",
)
