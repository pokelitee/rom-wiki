from __future__ import annotations

import struct

from romwiki.schema import NpcTrade, RecordProvenance
from romwiki.util.errors import InvalidRomError

NPC_TRADE_RECORD_SIZE = 84


def parse_npc_trade_record(
    data: bytes,
    *,
    trade_id: int,
    nickname: str,
    ot_name: str,
    archive_path: str,
) -> NpcTrade:
    if len(data) != NPC_TRADE_RECORD_SIZE:
        raise InvalidRomError(
            f"HGSS NPC trade {trade_id} has size {len(data)}, expected "
            f"{NPC_TRADE_RECORD_SIZE}"
        )

    offered_species_id = struct.unpack_from("<I", data, 0)[0]
    ivs = struct.unpack_from("<6I", data, 4)
    ot_id = struct.unpack_from("<H", data, 0x20)[0]
    held_item_id = struct.unpack_from("<I", data, 0x3C)[0]
    requested_species_id = struct.unpack_from("<I", data, 0x4C)[0]
    trailing_padding = struct.unpack_from("<I", data, 0x50)[0]

    if not 1 <= offered_species_id <= 493:
        raise InvalidRomError(
            f"HGSS NPC trade {trade_id} has invalid offered species "
            f"{offered_species_id}"
        )
    if not 1 <= requested_species_id <= 493:
        raise InvalidRomError(
            f"HGSS NPC trade {trade_id} has invalid requested species "
            f"{requested_species_id}"
        )
    if any(iv > 31 for iv in ivs):
        raise InvalidRomError(f"HGSS NPC trade {trade_id} has an invalid IV")
    if held_item_id >= 537:
        raise InvalidRomError(
            f"HGSS NPC trade {trade_id} has invalid held item {held_item_id}"
        )
    if trailing_padding:
        raise InvalidRomError(f"HGSS NPC trade {trade_id} has nonzero padding")

    return NpcTrade(
        trade_id=trade_id,
        nickname=nickname,
        ot_name=ot_name,
        ot_id=ot_id,
        offered_species_id=offered_species_id,
        offered_forme_id=0,
        requested_species_id=requested_species_id,
        held_item_id=held_item_id or None,
        ivs=ivs,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=trade_id
        ),
    )
