from romwiki.schema.egg_moves import Gen4EggMoveSet
from romwiki.schema.encounters import (
    EncounterLocation,
    EncounterMethod,
    Gen4EncounterArea,
    WalkingEncounterSlot,
    WaterEncounterSlot,
)
from romwiki.schema.evolutions import EvolutionEntry, Gen4EvolutionSet
from romwiki.schema.items import Gen4Item, ItemPartyEffects
from romwiki.schema.learnsets import Gen4LevelUpLearnset, LevelUpMove
from romwiki.schema.locations import (
    BonusEncounterSpecies,
    Gen4Location,
    LocationConnection,
    LocationDailyEncounterPool,
    LocationHoneyTree,
    LocationItem,
    LocationNpcTrade,
    LocationPokemonGift,
    LocationRoamingActivation,
    LocationShop,
    LocationShopItem,
    LocationStaticEncounter,
    LocationTrainerReference,
    LocationWarp,
)
from romwiki.schema.machines import Gen4Machine
from romwiki.schema.moves import Gen4Move
from romwiki.schema.pokemon import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.schema.trainers import (
    Gen4Trainer,
    TrainerLocation,
    TrainerPokemon,
    TrainerScriptReference,
)
from romwiki.schema.tutors import (
    Gen4SpecialTutorMove,
    Gen4TutorCompatibility,
    Gen4TutorMove,
    ShardCosts,
)

__all__ = [
    "PokemonPersonalData",
    "RecordProvenance",
    "StatBlock",
    "WildHeldItems",
    "EncounterMethod",
    "EncounterLocation",
    "Gen4EncounterArea",
    "WalkingEncounterSlot",
    "WaterEncounterSlot",
    "Gen4Trainer",
    "TrainerPokemon",
    "TrainerLocation",
    "TrainerScriptReference",
    "Gen4Location",
    "LocationConnection",
    "LocationItem",
    "LocationShop",
    "LocationPokemonGift",
    "LocationNpcTrade",
    "LocationRoamingActivation",
    "LocationStaticEncounter",
    "LocationShopItem",
    "LocationTrainerReference",
    "LocationWarp",
    "LocationHoneyTree",
    "LocationDailyEncounterPool",
    "BonusEncounterSpecies",
    "Gen4Move",
    "Gen4LevelUpLearnset",
    "LevelUpMove",
    "Gen4EggMoveSet",
    "Gen4Item",
    "ItemPartyEffects",
    "EvolutionEntry",
    "Gen4EvolutionSet",
    "Gen4Machine",
    "Gen4TutorCompatibility",
    "Gen4TutorMove",
    "Gen4SpecialTutorMove",
    "ShardCosts",
]
