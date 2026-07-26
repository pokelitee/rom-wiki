from __future__ import annotations

from pathlib import Path
from typing import Any

from romwiki.engines.registry import get_engine
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.registry import get_platform
from romwiki.schema.versions import NPC_TRADES_RAW_SCHEMA_VERSION
from romwiki.util.errors import InvalidRomError, ProfileError
from romwiki.util.json_io import write_json_atomic


def extract_npc_trade_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trade extraction")
    profile = result.match.profile
    try:
        trades_path = profile.layout["npc_trades"]
        messages_path = profile.layout["messages"]
        trade_names_member = profile.parameters["npc_trade_names_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing NPC trade metadata: {error.args[0]}"
        ) from error
    unused_trade_ids = frozenset(profile.parameters.get("npc_trades_unused", ()))

    platform = get_platform(profile.platform)
    engine = get_engine(profile.engine).trades
    filesystem = platform.filesystem_from_image(result.image)
    trades = platform.archive_cls.from_bytes(filesystem.read(trades_path))
    messages = platform.archive_cls.from_bytes(filesystem.read(messages_path))
    trade_strings = engine.parse_english_message_archive(
        messages.read(trade_names_member)
    )
    if len(trade_strings) != len(trades.members) * 2:
        raise InvalidRomError(
            "NPC trade name bank must contain one nickname and OT name per trade"
        )

    records = []
    for member in trades.members:
        if member.index in unused_trade_ids:
            continue
        records.append(
            engine.parse_npc_trade_record(
                trades.read(member.index),
                trade_id=member.index,
                nickname=trade_strings[member.index * 2],
                ot_name=trade_strings[member.index * 2 + 1],
                archive_path=trades_path,
            ).to_dict()
        )
    return {
        "schema_version": NPC_TRADES_RAW_SCHEMA_VERSION,
        "game": profile.id,
        "engine": profile.engine,
        "dataset": "trades",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "archive": trades_path,
            "trade_names": {"archive": messages_path, "member": trade_names_member},
        },
        "records": records,
    }


def write_npc_trade_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    write_json_atomic(output_path, dataset)
