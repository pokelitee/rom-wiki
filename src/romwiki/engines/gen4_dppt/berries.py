from __future__ import annotations

import struct
from dataclasses import dataclass

from romwiki.util.errors import InvalidRomError

GEN4_BERRY_FIRMNESS_NAMES = {
    1: "Very Soft",
    2: "Soft",
    3: "Hard",
    4: "Very Hard",
    5: "Super Hard",
}


@dataclass(frozen=True, slots=True)
class Gen4BerryData:
    size: int
    firmness: int
    base_yield: int
    stage_duration: int
    moisture_drain_rate: int
    spiciness: int
    dryness: int
    sweetness: int
    bitterness: int
    sourness: int
    smoothness: int


def parse_berry_record(data: bytes) -> Gen4BerryData:
    if len(data) < 11:
        raise InvalidRomError("Gen IV berry record is too small")
    (
        size,
        firmness,
        base_yield,
        stage_duration,
        moisture_drain_rate,
        spiciness,
        dryness,
        sweetness,
        bitterness,
        sourness,
        smoothness,
    ) = struct.unpack_from("<HBBBBBBBBBB", data, 0)
    return Gen4BerryData(
        size=size,
        firmness=firmness,
        base_yield=base_yield,
        stage_duration=stage_duration,
        moisture_drain_rate=moisture_drain_rate,
        spiciness=spiciness,
        dryness=dryness,
        sweetness=sweetness,
        bitterness=bitterness,
        sourness=sourness,
        smoothness=smoothness,
    )
