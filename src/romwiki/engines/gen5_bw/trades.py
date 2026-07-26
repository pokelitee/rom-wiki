from __future__ import annotations

import struct

from romwiki.schema import Gen5NpcTrade, RecordProvenance
from romwiki.util.errors import InvalidRomError

# `InGameTrades` (Ajarmar/universal-pokemon-randomizer-zx's Gen5RomHandler.java
# `getIngameTrades`): one 108-byte record per member. Verified against 5 real
# Black ROM trades (species/item/OT name/nickname all cross-checked against
# the real in-game trades): "Lillil" the Petilil for a Cottonee, "Redeye" the
# red-striped Basculin for a Minccino, "Minipete" the Emolga for a Boldore,
# "Gorge" the Munchlax for a Cinccino, and "Eeks" the Rotom for a Ditto -- all
# real, correct, and exactly matching the known real trade NPCs. Each
# version-exclusive species (e.g. Black's Cottonee-for-Petilil counterpart)
# has its own inactive record in the same archive, filtered by the ROM's own
# `TradesUnused` index list rather than decoded as if it were live.
TRADE_RECORD_SIZE = 108
_OFFERED_SPECIES_OFFSET = 4
_OFFERED_FORME_OFFSET = 8
_IVS_OFFSET = 0x10
_OT_ID_OFFSET = 0x34
_HELD_ITEM_OFFSET = 0x4C
_REQUESTED_SPECIES_OFFSET = 0x5C


def parse_npc_trade_record(
    data: bytes,
    *,
    trade_id: int,
    nickname: str,
    ot_name: str,
    archive_path: str,
) -> Gen5NpcTrade:
    if len(data) != TRADE_RECORD_SIZE:
        raise InvalidRomError(
            f"Gen V NPC trade {trade_id} has size {len(data)}, expected "
            f"{TRADE_RECORD_SIZE}"
        )
    offered_species_id = struct.unpack_from("<I", data, _OFFERED_SPECIES_OFFSET)[0]
    offered_forme_id = struct.unpack_from("<I", data, _OFFERED_FORME_OFFSET)[0]
    ivs = struct.unpack_from("<6I", data, _IVS_OFFSET)
    ot_id = struct.unpack_from("<H", data, _OT_ID_OFFSET)[0]
    held_item_id = struct.unpack_from("<I", data, _HELD_ITEM_OFFSET)[0]
    requested_species_id = struct.unpack_from("<I", data, _REQUESTED_SPECIES_OFFSET)[0]
    return Gen5NpcTrade(
        trade_id=trade_id,
        nickname=nickname,
        ot_name=ot_name,
        ot_id=ot_id,
        offered_species_id=offered_species_id,
        offered_forme_id=offered_forme_id,
        requested_species_id=requested_species_id,
        held_item_id=held_item_id or None,
        ivs=ivs,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=trade_id
        ),
    )
