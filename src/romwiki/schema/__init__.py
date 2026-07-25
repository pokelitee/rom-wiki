from romwiki.schema.egg_moves import Gen4EggMoveSet, Gen5EggMoveSet
from romwiki.schema.encounters import (
    EncounterLocation,
    EncounterMethod,
    Gen4EncounterArea,
    Gen5EncounterArea,
    Gen5EncounterMethod,
    Gen5EncounterSlot,
    WalkingEncounterSlot,
    WaterEncounterSlot,
)
from romwiki.schema.evolutions import EvolutionEntry, Gen4EvolutionSet
from romwiki.schema.items import (
    Gen4Item,
    Gen5Item,
    Gen5ItemPartyEffects,
    ItemPartyEffects,
)
from romwiki.schema.learnsets import Gen4LevelUpLearnset, LevelUpMove
from romwiki.schema.locations import (
    BonusEncounterSpecies,
    Gen4Location,
    Gen5Location,
    LocationConnection,
    LocationDailyEncounterPool,
    LocationGameCornerPrize,
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
from romwiki.schema.marts import Gen5Shop
from romwiki.schema.moves import Gen4Move, Gen5Move
from romwiki.schema.pickup import Gen4PickupTables, Gen5PickupTable
from romwiki.schema.pokemon import (
    PokemonPersonalData,
    RecordProvenance,
    StatBlock,
    WildHeldItems,
)
from romwiki.schema.static_encounters import Gen5StaticEncounter
from romwiki.schema.trades import Gen5NpcTrade
from romwiki.schema.trainers import (
    Gen4Trainer,
    Gen5Trainer,
    Gen5TrainerPokemon,
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
    "Gen5EncounterArea",
    "Gen5EncounterMethod",
    "Gen5EncounterSlot",
    "WalkingEncounterSlot",
    "WaterEncounterSlot",
    "Gen4Trainer",
    "Gen5Trainer",
    "Gen5TrainerPokemon",
    "TrainerPokemon",
    "TrainerLocation",
    "TrainerScriptReference",
    "Gen4Location",
    "Gen5Location",
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
    "LocationGameCornerPrize",
    "Gen4Move",
    "Gen5Move",
    "Gen4LevelUpLearnset",
    "LevelUpMove",
    "Gen4EggMoveSet",
    "Gen5EggMoveSet",
    "Gen4Item",
    "Gen5Item",
    "Gen5ItemPartyEffects",
    "ItemPartyEffects",
    "EvolutionEntry",
    "Gen4EvolutionSet",
    "Gen4Machine",
    "Gen4PickupTables",
    "Gen5PickupTable",
    "Gen5StaticEncounter",
    "Gen5Shop",
    "Gen5NpcTrade",
    "Gen4TutorCompatibility",
    "Gen4TutorMove",
    "Gen4SpecialTutorMove",
    "ShardCosts",
]
