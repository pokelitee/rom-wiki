# Data Sources

The primary source is Renegade Platinum standard v1.3.0. Structured reference data
from PokéDB and explicit annotations may supplement facts that are not represented
directly in table-driven ROM data.

Record-level provenance is included in normalized datasets and generated pages,
including separate archive/member references for Pokémon personal data and
level-up learnsets, evolution records, and the ROM item-name catalog.
Wild held-item slot IDs come from each Pokémon personal record; PokéDB resolves
their stable display names.
Visible item pickups come from Poké Ball object events, while hidden pickups come
from background-event records. Item IDs are decoded from their standard Gen IV
script ranges and named with the ROM item-name catalog.
Common Poké Mart stock and badge requirements come from the shared ARM9
progression table. Specialty inventories come from the ARM9 inventory pointer
table selected by each clerk's field-script command. Prices come from Renegade
Platinum's item-data records.
Veilstone decoration and Sunyshore weekday seal inventories use distinct field
commands and catalog-name message banks. Their prices come from the 28-byte goods
records and 10-byte seal records in ARM9, respectively.
Battle Frontier inventory IDs come from the dedicated field command used by its
exchange counters. Exact item costs come from the 41-entry BP price table in ARM9
overlay 7.
Direct Pokémon gifts are decoded from literal `GivePokemon` field commands,
including their level and held item. Togepi, Riolu, and Manaphy eggs come from
profile-anchored `GiveEgg` commands because that opcode has no reliable adjacent
signature for distinguishing commands from operands. Conditional script branches
can make listed gift outcomes mutually exclusive.
Static encounters are decoded from literal `WildBattle` and `LegendaryBattle`
field commands followed by Platinum's battle-result check. Shared script member
401 uses explicit map-header annotations to associate Articuno, Moltres, Lugia,
and Kyogre with the object events that invoke their script entries. Commands whose
species or level comes from a script variable are excluded until their control
flow can be resolved exactly.
Egg move lists and their ordering come from the packed species table in ARM9
overlay 5; each extracted set retains its exact overlay offset.
TM/HM assignments come from the profile's exact ROM-offset table and are joined
with compatibility bits from each Pokémon personal record.
Shard move-tutor assignments, costs, location IDs, and 505 Pokémon/form
compatibility rows come from exact tables in ARM9 overlay 5. Location display
names are explicit profile metadata.

Draco Meteor and the three starter ultimate moves are decoded from exact move
assignments in field-script members 450 and 493. Their type or species
eligibility checks are decoded from the same scripts and joined to the ROM's
personal records. The Route 210 and Route 228 display names and maximum-friendship
requirement are explicit profile metadata. Static compatibility follows the
personal-record types and does not model temporary or held-item-driven type
changes.
