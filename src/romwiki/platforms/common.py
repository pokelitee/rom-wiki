from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import BinaryIO

_HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RomHashes:
    md5: str
    sha1: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def calculate_hashes(stream: BinaryIO) -> RomHashes:
    digests = {
        "md5": hashlib.md5(usedforsecurity=False),
        "sha1": hashlib.sha1(usedforsecurity=False),
        "sha256": hashlib.sha256(),
    }
    while chunk := stream.read(_HASH_CHUNK_SIZE):
        for digest in digests.values():
            digest.update(chunk)
    return RomHashes(**{name: digest.hexdigest() for name, digest in digests.items()})
