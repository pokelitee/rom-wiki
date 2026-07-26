from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from romwiki.platforms.nds.reader import NintendoDSImage
from romwiki.util.errors import InvalidRomError

_ROOT_DIRECTORY_ID = 0xF000


@dataclass(frozen=True, slots=True)
class NintendoDSFile:
    id: int
    path: PurePosixPath | None
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start

    @property
    def display_path(self) -> str:
        return str(self.path) if self.path is not None else f"<unnamed>/{self.id}.bin"


class NintendoDSFileSystem:
    def __init__(self, image_path: Path, files: tuple[NintendoDSFile, ...]) -> None:
        self.image_path = image_path
        self.files = files
        self._files_by_path = {
            str(file.path): file for file in files if file.path is not None
        }

    @classmethod
    def from_image(cls, image: NintendoDSImage) -> NintendoDSFileSystem:
        header = image.header
        with image.path.open("rb") as stream:
            stream.seek(header.file_name_table_offset)
            fnt = stream.read(header.file_name_table_size)
            stream.seek(header.file_allocation_table_offset)
            fat = stream.read(header.file_allocation_table_size)

        if len(fnt) != header.file_name_table_size:
            raise InvalidRomError("Nintendo DS filename table is truncated")
        if len(fat) != header.file_allocation_table_size:
            raise InvalidRomError("Nintendo DS file allocation table is truncated")

        paths_by_id = _parse_filename_table(fnt, len(fat) // 8)
        files = []
        for file_id, (start, end) in enumerate(struct.iter_unpack("<II", fat)):
            if start > end or end > image.size:
                raise InvalidRomError(
                    f"Nintendo DS file {file_id} has invalid bounds {start}:{end}"
                )
            files.append(
                NintendoDSFile(
                    id=file_id,
                    path=paths_by_id.get(file_id),
                    start=start,
                    end=end,
                )
            )
        return cls(image.path, tuple(files))

    def get(self, path: str | PurePosixPath) -> NintendoDSFile:
        normalized = str(PurePosixPath(path))
        try:
            return self._files_by_path[normalized]
        except KeyError as error:
            raise InvalidRomError(
                f"ROM filesystem path does not exist: {normalized}"
            ) from error

    def read(self, file: NintendoDSFile | str | PurePosixPath) -> bytes:
        entry = self.get(file) if isinstance(file, (str, PurePosixPath)) else file
        with self.image_path.open("rb") as stream:
            stream.seek(entry.start)
            data = stream.read(entry.size)
        if len(data) != entry.size:
            raise InvalidRomError(f"ROM file is truncated: {entry.display_path}")
        return data

    def read_magic(self, file: NintendoDSFile, length: int = 4) -> bytes:
        with self.image_path.open("rb") as stream:
            stream.seek(file.start)
            return stream.read(min(length, file.size))


def _parse_filename_table(data: bytes, file_count: int) -> dict[int, PurePosixPath]:
    if len(data) < 8:
        raise InvalidRomError("Nintendo DS filename table is too small")
    directory_count = struct.unpack_from("<H", data, 6)[0]
    if directory_count == 0 or directory_count * 8 > len(data):
        raise InvalidRomError(
            "Nintendo DS filename table has an invalid directory count"
        )

    directories = []
    for index in range(directory_count):
        subtable_offset, first_file_id, parent_id = struct.unpack_from(
            "<IHH", data, index * 8
        )
        if subtable_offset >= len(data):
            raise InvalidRomError("Nintendo DS directory subtable is out of bounds")
        directories.append((subtable_offset, first_file_id, parent_id))

    paths_by_id: dict[int, PurePosixPath] = {}
    visited: set[int] = set()

    def visit(directory_id: int, parent_path: PurePosixPath) -> None:
        index = directory_id - _ROOT_DIRECTORY_ID
        if not 0 <= index < directory_count:
            raise InvalidRomError(
                f"Invalid Nintendo DS directory ID: {directory_id:#x}"
            )
        if directory_id in visited:
            raise InvalidRomError(
                "Nintendo DS filename table contains a directory cycle"
            )
        visited.add(directory_id)

        position, file_id, _ = directories[index]
        while True:
            if position >= len(data):
                raise InvalidRomError("Nintendo DS directory subtable is unterminated")
            control = data[position]
            position += 1
            if control == 0:
                break

            name_length = control & 0x7F
            if name_length == 0 or position + name_length > len(data):
                raise InvalidRomError("Nintendo DS filename has an invalid length")
            name = _decode_path_segment(data[position : position + name_length])
            position += name_length
            path = parent_path / name

            if control & 0x80:
                if position + 2 > len(data):
                    raise InvalidRomError("Nintendo DS child directory ID is truncated")
                child_id = struct.unpack_from("<H", data, position)[0]
                position += 2
                visit(child_id, path)
            else:
                if file_id >= file_count or file_id in paths_by_id:
                    raise InvalidRomError(f"Invalid Nintendo DS file ID: {file_id}")
                paths_by_id[file_id] = path
                file_id += 1

    visit(_ROOT_DIRECTORY_ID, PurePosixPath())
    if len(visited) != directory_count:
        raise InvalidRomError("Nintendo DS filename table contains orphan directories")
    return paths_by_id


def _decode_path_segment(value: bytes) -> str:
    try:
        name = value.decode("ascii")
    except UnicodeDecodeError as error:
        raise InvalidRomError("Nintendo DS filename is not ASCII") from error
    if name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
        raise InvalidRomError(f"Unsafe Nintendo DS filename: {name!r}")
    return name
