# Data Sources

The primary source is the exact USA retail release of Pokémon Platinum
(header code CPUE, ROM version 0), the same clean image used as Renegade
Platinum's comparison baseline. Structured reference data from PokéDB and
explicit annotations may supplement facts that are not represented directly
in table-driven ROM data.

Type names are decoded from message member 624, and move names are decoded
from message member 647. The normalized datasets preserve their native IDs,
decoded names, and message-table provenance. Comparing those move names with
PokéDB confirms canonical Generation IV naming and leaves the ROM name
authoritative.

Record-level provenance is included in normalized datasets and generated
pages, including separate archive/member references for Pokémon personal
data and level-up learnsets, evolution records, and the ROM item-name
catalog. Wild held-item slot IDs come from each Pokémon personal record.
Display names come from ROM message member 392; PokéDB supplies stable page
slugs without overriding those names.

Ability names are decoded from the same profile-defined name-source table as
Pokémon, move, and item names; PokéDB again supplies the stable page slug
rather than overriding the ROM name. Pickup and Honey Gather's held-item
tables come from the same ARM9 tables used on their assigned Pokémon's
pages.

Visible item pickups come from Poké Ball object events, while hidden pickups
come from background-event records. Item IDs are decoded from their standard
Gen IV script ranges and named with the ROM item-name catalog.

Common Poké Mart stock and badge requirements come from the shared ARM9
progression table. Specialty inventories come from the ARM9 inventory
pointer table selected by each clerk's field-script command. Prices come
from Platinum's item-data records.

The 34-byte item records also provide price, pocket, held-effect
parameters, Fling and Natural Gift properties, usability flags, and
party-use parameters. Item IDs are joined to those records through the
complete mapping table discovered and validated in ARM9 rather than by
assuming the ID equals the archive member, the same verification applied
across every supported release regardless of whether a given build actually
repurposes any slots.

Veilstone decoration and Sunyshore weekday seal inventories use distinct
field commands and catalog-name message banks. Their prices come from the
28-byte goods records and 10-byte seal records in ARM9, respectively.

Battle Frontier inventory IDs come from the dedicated field command used by
its exchange counters. Exact item costs come from the 41-entry BP price
table in ARM9 overlay 7.

Direct Pokémon gifts are decoded from literal `GivePokemon` field commands,
including their level and held item. Togepi and Riolu eggs come from
profile-anchored `GiveEgg` commands because that opcode has no reliable
adjacent signature for distinguishing commands from operands. Conditional
script branches can make listed gift outcomes mutually exclusive.

In-game trades are joined from literal `InitNPCTrade`/`StartNPCTrade` field
command sequences and the four 80-byte records in
`fielddata/pokemon_trade/fld_trade.narc`. Each record supplies the requested
and offered species, fixed IVs, personality-derived nature, held item, OT
metadata, and language. Nicknames and OT names come from ROM message member
370; the received Pokémon inherits the level of the Pokémon traded away.

Static encounters are decoded from literal `WildBattle`, `LegendaryBattle`,
`FatefulEncounter`, and `GiratinaOriginBattle` field commands followed by
Platinum's battle-result check. The latter two preserve the
encounter-specific setup used at Flower Paradise and in the Distortion
World. Commands whose species or level comes from a script variable are
excluded until their control flow can be resolved exactly.

Roaming Pokémon are audited through Platinum's one-byte
`ActivateRoamingPokemon` slot command. This release invokes four of the five
slots: Mesprit (slot 0), Cresselia (slot 1), and Moltres and Zapdos (slots 3
and 4), each released by its own story event (the Lake Verity disturbance,
the Fullmoon Island request, and the Eterna Team Galactic Building battle,
respectively). The fifth slot has no invoking script in this release and is
reported as inactive rather than assumed.

Egg move lists and their ordering come from the packed species table in
ARM9 overlay 5; each extracted set retains its exact overlay offset.

TM/HM assignments come from the profile's exact ROM-offset table and are
joined with compatibility bits from each Pokémon personal record.

Shard move-tutor assignments, costs, location IDs, and 505 Pokémon/form
compatibility rows come from exact tables in ARM9 overlay 5. Location
display names are explicit profile metadata.

Draco Meteor and the three starter ultimate moves are decoded from exact
move assignments in field-script members 450 and 493. Their type or species
eligibility checks are decoded from the same scripts and joined to the
ROM's personal records. The Route 210 and Route 228 display names and
maximum-friendship requirement are explicit profile metadata. Static
compatibility follows the personal-record types and does not model
temporary or held-item-driven type changes.
