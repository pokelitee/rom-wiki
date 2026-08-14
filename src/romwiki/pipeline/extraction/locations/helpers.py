from __future__ import annotations

from collections import defaultdict
from typing import Any

from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.pipeline.extraction.trainers.dispatcher import extract_trainer_dataset
from romwiki.schema import (
    LocationConnection,
    LocationItem,
    LocationTrainerReference,
)
from romwiki.util.errors import InvalidRomError


def extract_event_map_items(
    engine: Any, events: Any, item_names: tuple[str, ...]
) -> tuple[LocationItem, ...]:
    items = []
    for event in events.objects:
        item_id = engine.resolve_visible_item_id(event, item_count=len(item_names))
        if item_id is None:
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=item_names[item_id],
                kind="visible",
                event_index=event.index,
                x=event.x,
                z=event.z,
                y=event.y,
                hidden_flag=event.hidden_flag,
            )
        )
    for event in events.backgrounds:
        item_id = engine.resolve_hidden_item_id(event, item_count=len(item_names))
        if item_id is None:
            continue
        items.append(
            LocationItem(
                item_id=item_id,
                name=item_names[item_id],
                kind="hidden",
                event_index=event.index,
                x=event.x,
                z=event.z,
                y=event.y,
                hidden_flag=None,
            )
        )
    return tuple(items)


def extract_event_map_connections(
    engine: Any,
    headers: tuple[Any, ...],
    matrices: Any,
    location_names: tuple[str, ...],
    void_header_ids: frozenset[int],
) -> dict[int, list[LocationConnection]]:
    directions: dict[int, dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for matrix_id in sorted({header.matrix_id for header in headers}):
        if matrix_id >= len(matrices.members):
            raise InvalidRomError(f"Map header references missing matrix {matrix_id}")
        matrix = engine.parse_map_matrix(matrices.read(matrix_id), matrix_id=matrix_id)
        if matrix.header_ids is None:
            continue
        for index, source in enumerate(matrix.header_ids):
            if source in void_header_ids:
                continue
            if source >= len(headers):
                raise InvalidRomError(
                    f"Map matrix {matrix_id} references missing header {source}"
                )
            x = index % matrix.width
            z = index // matrix.width
            for offset, forward, reverse in (
                (1, "east", "west"),
                (matrix.width, "south", "north"),
            ):
                if (forward == "east" and x + 1 >= matrix.width) or (
                    forward == "south" and z + 1 >= matrix.height
                ):
                    continue
                destination = matrix.header_ids[index + offset]
                if destination == source or destination in void_header_ids:
                    continue
                if destination >= len(headers):
                    raise InvalidRomError(
                        f"Map matrix {matrix_id} references missing header "
                        f"{destination}"
                    )
                directions[source][destination].add(forward)
                directions[destination][source].add(reverse)

    result = {}
    direction_order = {"north": 0, "east": 1, "south": 2, "west": 3}
    for source, destinations in directions.items():
        result[source] = []
        for destination_id, values in sorted(destinations.items()):
            destination = headers[destination_id]
            result[source].append(
                LocationConnection(
                    destination_header_id=destination_id,
                    destination_name=location_names[destination.location_name_id],
                    destination_internal_name=destination.internal_name,
                    directions=tuple(sorted(values, key=direction_order.__getitem__)),
                )
            )
    return result


def extract_trainer_references(
    result: InspectionResult,
    trainer_dataset: dict[str, Any] | None = None,
) -> dict[int, list[LocationTrainerReference]]:
    references: dict[int, list[LocationTrainerReference]] = defaultdict(list)
    seen: set[tuple[int, int, str]] = set()
    trainers = trainer_dataset or extract_trainer_dataset(result)
    for trainer in trainers["records"]:
        if not trainer["party"]:
            continue
        for source, locations in (
            ("overworld-object", trainer["locations"]),
            ("map-script", trainer["script_references"]),
        ):
            for location in locations:
                key = (location["header_id"], trainer["trainer_id"], source)
                if key in seen:
                    continue
                seen.add(key)
                references[location["header_id"]].append(
                    LocationTrainerReference(
                        trainer_id=trainer["trainer_id"],
                        name=trainer["name"],
                        class_name=trainer["class_name"],
                        source=source,
                    )
                )
    for values in references.values():
        values.sort(key=lambda item: (item.class_name, item.name, item.trainer_id))
    return references
