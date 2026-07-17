# Data Sources

The primary source is Renegade Platinum standard v1.3.0. Structured reference data
from PokéDB and explicit annotations may supplement facts that are not represented
directly in table-driven ROM data.

Record-level provenance is included in normalized datasets and generated pages,
including separate archive/member references for Pokémon personal data and
level-up learnsets, evolution records, and the ROM item-name catalog.
TM/HM assignments come from the profile's exact ROM-offset table and are joined
with compatibility bits from each Pokémon personal record.
Shard move-tutor assignments, costs, location IDs, and 505 Pokémon/form
compatibility rows come from exact tables in ARM9 overlay 5. Location display
names are explicit profile metadata; all other tutor fields are decoded from the
ROM.
