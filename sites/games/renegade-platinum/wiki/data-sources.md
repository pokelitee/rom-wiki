# Data Sources

The primary source is Renegade Platinum standard v1.3.0. Structured reference data
from PokéDB and explicit annotations may supplement facts that are not represented
directly in table-driven ROM data.

Record-level provenance is included in normalized datasets and generated pages,
including separate archive/member references for Pokémon personal data and
level-up learnsets, evolution records, and the ROM item-name catalog.
Wild held-item slot IDs come from each Pokémon personal record; PokéDB resolves
their stable display names.
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
