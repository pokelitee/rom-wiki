from __future__ import annotations

from dataclasses import replace

from romwiki.platforms.registry import RomImage, get_platform
from romwiki.profiles.models import HashMatch, TableLocation

_POINTER_SIZE = 4


def locate_tables(match: HashMatch, image: RomImage) -> HashMatch:
    """Find each symbol-named table through the code that points to it.

    A ROM hack that moves a table repoints the retail code's references, so
    the words at the retail pointer sites hold the table's address in this
    image. The address is accepted only when every site agrees on one that
    lies inside the image; otherwise the profile's symbol offset stands. An
    offset the profile sets explicitly has no symbol and is never changed.
    """
    profile = match.profile
    read = get_platform(profile.platform).read_bytes
    if read is None:
        return match
    parameters = dict(profile.parameters)
    locations: dict[str, TableLocation] = {}
    for key, symbol in profile.symbols.items():
        if symbol.address is None or not symbol.pointers:
            continue
        values = {
            int.from_bytes(read(image, site, _POINTER_SIZE), "little")
            for site in symbol.pointers
            if site + _POINTER_SIZE <= image.size
        }
        offset = parameters[key]
        if len(values) == 1:
            located = offset + (values.pop() - symbol.address)
            if 0 <= located < image.size:
                parameters[key] = located
                locations[key] = (
                    TableLocation.SYMBOL if located == offset else TableLocation.POINTER
                )
                continue
        locations[key] = TableLocation.SYMBOL_UNCONFIRMED
    if not locations:
        return match
    located_profile = replace(profile, parameters=parameters, table_locations=locations)
    return replace(match, profile=located_profile)
