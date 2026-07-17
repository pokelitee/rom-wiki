from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from romwiki.engines.gen4_dppt import parse_english_message_archive, parse_trainer_record
from romwiki.errors import InvalidRomError, ProfileError
from romwiki.pipeline.identify import InspectionResult
from romwiki.platforms.nds import NarcArchive, NintendoDSFileSystem


def extract_trainer_dataset(result: InspectionResult) -> dict[str, Any]:
    if result.match is None:
        raise ProfileError("A known game profile is required for trainer extraction")
    profile = result.match.profile
    try:
        trainer_path = profile.layout["trainer_data"]
        party_path = profile.layout["trainer_parties"]
        messages_path = profile.layout["messages"]
        names_member = profile.parameters["trainer_names_member"]
        classes_member = profile.parameters["trainer_classes_member"]
    except KeyError as error:
        raise ProfileError(
            f"Profile {profile.id} is missing trainer metadata: {error.args[0]}"
        ) from error

    filesystem = NintendoDSFileSystem.from_image(result.image)
    trainers = NarcArchive.from_bytes(filesystem.read(trainer_path))
    parties = NarcArchive.from_bytes(filesystem.read(party_path))
    messages = NarcArchive.from_bytes(filesystem.read(messages_path))
    if len(trainers.members) != len(parties.members):
        raise InvalidRomError("Trainer data and party archives have different counts")
    names = parse_english_message_archive(messages.read(names_member))
    classes = parse_english_message_archive(messages.read(classes_member))
    if len(names) < len(trainers.members):
        raise InvalidRomError("Trainer name table is shorter than the trainer archive")

    records = [
        parse_trainer_record(
            trainers.read(member.index),
            parties.read(member.index),
            trainer_id=member.index,
            name=names[member.index],
            class_names=classes,
            trainer_archive=trainer_path,
            party_archive=party_path,
        ).to_dict()
        for member in trainers.members
    ]
    return {
        "schema_version": 1,
        "game": profile.id,
        "dataset": "trainers",
        "record_count": len(records),
        "source": {
            "rom_sha256": result.image.hashes.sha256,
            "trainer_archive": trainer_path,
            "party_archive": party_path,
            "trainer_names": {"archive": messages_path, "member": names_member},
            "trainer_classes": {"archive": messages_path, "member": classes_member},
        },
        "records": records,
    }


def write_trainer_dataset(dataset: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dataset, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output_path)
