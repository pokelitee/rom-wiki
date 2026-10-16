from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from romwiki.engines.gen4.hgss.headbutt import HeadbuttEncounter
from romwiki.engines.gen4.hgss.safari import SafariEncounter
from romwiki.engines.gen5.b2w2.hidden_grottos import (
    HiddenGrotto,
    hidden_grotto_id_for_dispatch,
)
from romwiki.engines.gen5.b2w2.swarms import SwarmEncounter
from romwiki.pipeline.extraction.encounters.conditional import (
    _extract_encounter_locations,
    _extract_headbutt_encounters,
    _extract_safari_encounters,
)
from romwiki.pipeline.extraction.encounters.dispatcher import (
    extract_encounter_dataset,
)
from romwiki.pipeline.extraction.encounters.seasonal import (
    _extract_hidden_grottos,
    _extract_seasonal_wild_map_names,
    _extract_swarms,
    extract_seasonal_encounter_dataset,
)
from romwiki.pipeline.extraction.identify import InspectionResult
from romwiki.profiles.models import GameProfile, HashMatch, KnownHash
from romwiki.schema.encounters import (
    ConditionalEncounterArea,
    EncounterMethod,
    SeasonalEncounterArea,
    SeasonalEncounterMethod,
)
from romwiki.schema.pokemon import RecordProvenance
from romwiki.util.errors import DataSourceError, InvalidRomError, ProfileError


def _profile(*, engine="gen4_platinum", layout=None, parameters=None) -> GameProfile:
    return GameProfile(
        id="test",
        name="Test",
        platform="nintendo-ds",
        engine=engine,
        base_game="platinum",
        game_codes=("CPUE",),
        rom_versions=(1,),
        hashes=(),
        layout=dict(layout or {}),
        parameters=dict(parameters or {}),
    )


def _result(profile: GameProfile | None) -> InspectionResult:
    image = Mock()
    image.hashes.sha256 = "romsha256"
    match = (
        HashMatch(
            profile=profile,
            known_hash=KnownHash(algorithm="sha256", value="romsha256", variant="v1"),
        )
        if profile
        else None
    )
    return InspectionResult(image=image, match=match)


def _archive(count: int, *, read=None) -> SimpleNamespace:
    return SimpleNamespace(
        members=[SimpleNamespace(index=index) for index in range(count)],
        read=read or (lambda index: f"member-{index}".encode()),
    )


def _platform(
    archives: dict[bytes, SimpleNamespace], *, overlay=None
) -> SimpleNamespace:
    archive_cls = Mock()
    archive_cls.from_bytes = Mock(side_effect=lambda data, **kwargs: archives[data])
    filesystem = SimpleNamespace(read=lambda path: path.encode())
    return SimpleNamespace(
        archive_cls=archive_cls,
        filesystem_from_image=Mock(return_value=filesystem),
        read_overlay_decompressed=overlay,
    )


def _fake_engine_adapter(*, encounters_format: str, concern: SimpleNamespace):
    return SimpleNamespace(
        formats=SimpleNamespace(encounters=encounters_format),
        encounters=concern,
        capabilities=frozenset(),
    )


def _location_header(
    header_id: int, *, encounter_id: int = 0, location_name_id: int = 0
) -> SimpleNamespace:
    return SimpleNamespace(
        header_id=header_id,
        internal_name=f"HEADER{header_id}",
        encounter_id=encounter_id,
        location_name_id=location_name_id,
    )


def _map_header(
    header_id: int, *, overworld_file_id: int | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        header_id=header_id,
        internal_name=f"HEADER{header_id}",
        name=f"Location {header_id}",
        overworld_file_id=overworld_file_id,
    )


def _conditional_area(area_id: int = 0, *, archive_path: str = "encounters.narc"):
    method = EncounterMethod(rate=0, slots=())
    return ConditionalEncounterArea(
        area_id=area_id,
        walking_rate=20,
        walking_slots=(),
        swarm_species_ids=(0, 0),
        day_species_ids=(0, 0),
        night_species_ids=(0, 0),
        radar_species_ids=(0, 0, 0, 0),
        encounter_form_rates=(0, 0, 0, 0, 0),
        unown_table_id=0,
        dual_slot_species_ids={},
        surf=method,
        old_rod=method,
        good_rod=method,
        super_rod=method,
        provenance=RecordProvenance(source="rom", archive=archive_path, member=area_id),
    )


def _seasonal_area(map_index: int, *, archive_path: str = "wild.narc", season=None):
    method = SeasonalEncounterMethod(rate=0, slots=())
    return SeasonalEncounterArea(
        area_id=map_index,
        map_index=map_index,
        season=season,
        grass_cave=method,
        doubles_grass=method,
        shaking_spots=method,
        surfing=method,
        surfing_spots=method,
        fishing=method,
        fishing_spots=method,
        provenance=RecordProvenance(
            source="rom", archive=archive_path, member=map_index
        ),
    )


class ExtractEncounterDatasetDispatchTests(unittest.TestCase):
    def test_raises_profile_error_without_match(self) -> None:
        with self.assertRaises(ProfileError):
            extract_encounter_dataset(_result(None))

    def test_dispatches_to_seasonal_extraction_for_seasonal_engines(self) -> None:
        profile = _profile(engine="gen5_bw", layout={"encounters": "wild.narc"})
        adapter = _fake_engine_adapter(
            encounters_format="seasonal", concern=SimpleNamespace()
        )
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.dispatcher.get_engine",
                return_value=adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.dispatcher.extract_seasonal_encounter_dataset"
            ) as seasonal,
        ):
            seasonal.return_value = {"dataset": "wild_encounters"}
            result = extract_encounter_dataset(_result(profile))

        seasonal.assert_called_once()
        self.assertEqual(result, {"dataset": "wild_encounters"})

    def test_raises_data_source_error_for_unsupported_format(self) -> None:
        profile = _profile()
        adapter = _fake_engine_adapter(
            encounters_format="unsupported", concern=SimpleNamespace()
        )
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.dispatcher.get_engine",
                return_value=adapter,
            ),
            self.assertRaisesRegex(DataSourceError, "Unsupported encounter format"),
        ):
            extract_encounter_dataset(_result(profile))

    def test_conditional_raises_profile_error_without_encounter_archive(self) -> None:
        profile = _profile(layout={})
        adapter = _fake_engine_adapter(
            encounters_format="conditional", concern=SimpleNamespace()
        )
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.dispatcher.get_engine",
                return_value=adapter,
            ),
            self.assertRaisesRegex(
                ProfileError, "does not define an encounter archive"
            ),
        ):
            extract_encounter_dataset(_result(profile))


class ConditionalEncounterDatasetIntegrationTests(unittest.TestCase):
    def test_builds_full_dataset_with_headbutt_and_safari_merged(self) -> None:
        profile = _profile(
            engine="gen4_hgss",
            layout={
                "encounters": "encounters.narc",
                "map_names": "map_names.bin",
                "messages": "messages.narc",
                "headbutt_encounters": "headbutt.narc",
                "safari_encounters": "safari.narc",
            },
            parameters={
                "map_header_offset": 0x10,
                "map_header_count": 2,
                "location_names_member": 4,
            },
        )
        result = _result(profile)
        archives = {
            b"encounters.narc": _archive(1),
            b"messages.narc": _archive(0),
            b"headbutt.narc": _archive(2),
            b"safari.narc": _archive(2),
        }
        platform = _platform(archives)
        safari_names = ("Plains", "Meadow")
        engine_concern = SimpleNamespace(
            ARCHIVE_MEMBER_NONE=0xFFFF,
            POKEMON_NAME_COUNT=493,
            SAFARI_AREA_NAMES=safari_names,
            parse_encounter_record=Mock(
                side_effect=lambda data, *, area_id, archive_path: _conditional_area(
                    area_id, archive_path=archive_path
                )
            ),
            parse_headbutt_record=Mock(
                side_effect=lambda data, *, header_id, archive_path, species_count: (
                    HeadbuttEncounter(
                        header_id=header_id,
                        pools={},
                        tree_groups=(),
                        provenance=RecordProvenance("rom", archive_path, header_id),
                    )
                    if header_id == 0
                    else None
                )
            ),
            parse_safari_encounter_record=Mock(
                side_effect=(
                    lambda data, *, safari_area_id, archive_path, species_count: (
                        SafariEncounter(
                            safari_area_id=safari_area_id,
                            area_name=safari_names[safari_area_id],
                            methods={},
                            provenance=RecordProvenance(
                                "rom", archive_path, safari_area_id
                            ),
                        )
                    )
                )
            ),
        )
        adapter = _fake_engine_adapter(
            encounters_format="conditional", concern=engine_concern
        )
        headers = (
            _location_header(0, encounter_id=0, location_name_id=0),
            _location_header(1, encounter_id=0xFFFF, location_name_id=1),
        )

        with (
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.dispatcher.get_engine",
                return_value=adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.get_engine",
                return_value=adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.read_code_binary",
                return_value=b"arm9",
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.resolve_map_headers",
                return_value=(headers, ("Route 1", "Route 2")),
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.extract_reference_names",
                return_value={"pokemon_names": ["Bulbasaur"], "name_sources": {}},
            ),
        ):
            dataset = extract_encounter_dataset(result)

        self.assertEqual(dataset["dataset"], "wild_encounters")
        self.assertEqual(dataset["record_count"], 4)
        self.assertEqual(
            [record["source_type"] for record in dataset["records"][1:]],
            ["headbutt", "safari-zone", "safari-zone"],
        )
        self.assertEqual(
            dataset["records"][0]["locations"],
            (
                {
                    "header_id": 0,
                    "internal_name": "HEADER0",
                    "location_name_id": 0,
                    "name": "Route 1",
                },
            ),
        )
        headbutt_record = dataset["records"][1]
        self.assertEqual(headbutt_record["area_id"], 1)
        self.assertEqual(
            headbutt_record["location"],
            {"header_id": 0, "internal_name": "HEADER0", "name": "Route 1"},
        )
        safari_records = dataset["records"][2:]
        self.assertEqual([record["area_id"] for record in safari_records], [2, 3])
        self.assertEqual(dataset["pokemon_names"], ["Bulbasaur"])
        self.assertEqual(
            dataset["source"],
            {
                "rom_sha256": "romsha256",
                "archive": "encounters.narc",
                "map_headers": {
                    "arm9_offset": 0x10,
                    "count": 2,
                    "internal_names": "map_names.bin",
                },
                "location_names": {"archive": "messages.narc", "member": 4},
            },
        )


class ExtractHeadbuttEncountersTests(unittest.TestCase):
    def test_returns_empty_list_when_archive_not_configured(self) -> None:
        profile = _profile(layout={})
        result = _result(profile)
        records = _extract_headbutt_encounters(
            result, SimpleNamespace(), _platform({}), None, first_area_id=0
        )
        self.assertEqual(records, [])

    def test_raises_invalid_rom_error_on_member_count_mismatch(self) -> None:
        profile = _profile(
            layout={"headbutt_encounters": "headbutt.narc"},
            parameters={"map_header_count": 3},
        )
        result = _result(profile)
        platform = _platform({b"headbutt.narc": _archive(2)})
        filesystem = platform.filesystem_from_image(result.image)
        with self.assertRaisesRegex(
            InvalidRomError, "Headbutt archive has 2 members, expected 3"
        ):
            _extract_headbutt_encounters(
                result, SimpleNamespace(), platform, filesystem, first_area_id=0
            )

    def test_skips_empty_records_and_merges_locations(self) -> None:
        profile = _profile(
            layout={
                "headbutt_encounters": "headbutt.narc",
                "messages": "messages.narc",
                "map_names": "map_names.bin",
            },
            parameters={
                "map_header_count": 2,
                "map_header_offset": 0x10,
                "location_names_member": 4,
            },
        )
        result = _result(profile)
        platform = _platform(
            {b"headbutt.narc": _archive(2), b"messages.narc": _archive(0)}
        )
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(
            POKEMON_NAME_COUNT=493,
            parse_headbutt_record=Mock(
                side_effect=lambda data, *, header_id, archive_path, species_count: (
                    HeadbuttEncounter(
                        header_id=header_id,
                        pools={},
                        tree_groups=(),
                        provenance=RecordProvenance("rom", archive_path, header_id),
                    )
                    if header_id == 0
                    else None
                )
            ),
        )
        headers = (
            _location_header(0, location_name_id=0),
            _location_header(1, location_name_id=1),
        )
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.read_code_binary",
                return_value=b"arm9",
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.resolve_map_headers",
                return_value=(headers, ("Route 1", "Route 2")),
            ),
        ):
            records = _extract_headbutt_encounters(
                result, engine, platform, filesystem, first_area_id=5
            )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["area_id"], 5)
        self.assertEqual(record["source_type"], "headbutt")
        self.assertEqual(record["header_id"], 0)
        self.assertEqual(
            record["location"],
            {"header_id": 0, "internal_name": "HEADER0", "name": "Route 1"},
        )


class ExtractSafariEncountersTests(unittest.TestCase):
    def test_returns_empty_list_when_archive_not_configured(self) -> None:
        profile = _profile(layout={})
        result = _result(profile)
        records = _extract_safari_encounters(
            result, SimpleNamespace(), _platform({}), None, first_area_id=0
        )
        self.assertEqual(records, [])

    def test_raises_invalid_rom_error_on_member_count_mismatch(self) -> None:
        profile = _profile(layout={"safari_encounters": "safari.narc"})
        result = _result(profile)
        platform = _platform({b"safari.narc": _archive(1)})
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(
            SAFARI_AREA_NAMES=("Plains", "Meadow"), POKEMON_NAME_COUNT=493
        )
        with self.assertRaisesRegex(
            InvalidRomError, "Safari Zone archive has 1 members, expected 2"
        ):
            _extract_safari_encounters(
                result, engine, platform, filesystem, first_area_id=0
            )

    def test_success_builds_one_record_per_member(self) -> None:
        profile = _profile(layout={"safari_encounters": "safari.narc"})
        result = _result(profile)
        platform = _platform({b"safari.narc": _archive(2)})
        filesystem = platform.filesystem_from_image(result.image)
        names = ("Plains", "Meadow")
        engine = SimpleNamespace(
            SAFARI_AREA_NAMES=names,
            POKEMON_NAME_COUNT=493,
            parse_safari_encounter_record=Mock(
                side_effect=(
                    lambda data, *, safari_area_id, archive_path, species_count: (
                        SafariEncounter(
                            safari_area_id=safari_area_id,
                            area_name=names[safari_area_id],
                            methods={},
                            provenance=RecordProvenance(
                                "rom", archive_path, safari_area_id
                            ),
                        )
                    )
                )
            ),
        )
        records = _extract_safari_encounters(
            result, engine, platform, filesystem, first_area_id=3
        )
        self.assertEqual([record["area_id"] for record in records], [3, 4])
        self.assertEqual(
            [record["source_type"] for record in records],
            ["safari-zone", "safari-zone"],
        )
        self.assertEqual(
            [record["area_name"] for record in records], ["Plains", "Meadow"]
        )


class ExtractEncounterLocationsTests(unittest.TestCase):
    def test_raises_profile_error_when_metadata_missing(self) -> None:
        profile = _profile(layout={}, parameters={})
        result = _result(profile)
        platform = _platform({})
        with self.assertRaisesRegex(
            ProfileError, "missing encounter location metadata"
        ):
            _extract_encounter_locations(
                SimpleNamespace(), platform, result, None, encounter_count=1
            )

    def test_raises_invalid_rom_error_for_out_of_range_encounter_id(self) -> None:
        profile = _profile(
            layout={"map_names": "map_names.bin", "messages": "messages.narc"},
            parameters={
                "map_header_offset": 0,
                "map_header_count": 1,
                "location_names_member": 0,
            },
        )
        result = _result(profile)
        platform = _platform({b"messages.narc": _archive(0)})
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(ARCHIVE_MEMBER_NONE=0xFFFF)
        headers = (_location_header(0, encounter_id=5, location_name_id=0),)
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.read_code_binary",
                return_value=b"arm9",
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.resolve_map_headers",
                return_value=(headers, ("Route 1",)),
            ),
            self.assertRaisesRegex(
                InvalidRomError, "references missing encounter member 5"
            ),
        ):
            _extract_encounter_locations(
                engine, platform, result, filesystem, encounter_count=1
            )

    def test_skips_headers_with_null_encounter_id_and_groups_others(self) -> None:
        profile = _profile(
            layout={"map_names": "map_names.bin", "messages": "messages.narc"},
            parameters={
                "map_header_offset": 0,
                "map_header_count": 3,
                "location_names_member": 0,
            },
        )
        result = _result(profile)
        platform = _platform({b"messages.narc": _archive(0)})
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(ARCHIVE_MEMBER_NONE=0xFFFF)
        headers = (
            _location_header(0, encounter_id=0xFFFF, location_name_id=0),
            _location_header(1, encounter_id=0, location_name_id=1),
            _location_header(2, encounter_id=0, location_name_id=2),
        )
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.read_code_binary",
                return_value=b"arm9",
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.resolve_map_headers",
                return_value=(headers, ("R0", "R1", "R2")),
            ),
        ):
            locations, source = _extract_encounter_locations(
                engine, platform, result, filesystem, encounter_count=1
            )

        self.assertEqual(set(locations.keys()), {0})
        self.assertEqual([location.header_id for location in locations[0]], [1, 2])
        self.assertEqual(
            source,
            {
                "map_headers": {
                    "arm9_offset": 0,
                    "count": 3,
                    "internal_names": "map_names.bin",
                },
                "location_names": {"archive": "messages.narc", "member": 0},
            },
        )

    def test_uses_profile_override_for_null_encounter_id(self) -> None:
        profile = _profile(
            layout={"map_names": "map_names.bin", "messages": "messages.narc"},
            parameters={
                "map_header_offset": 0,
                "map_header_count": 1,
                "location_names_member": 0,
                "null_encounter_id": 99,
            },
        )
        result = _result(profile)
        platform = _platform({b"messages.narc": _archive(0)})
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(ARCHIVE_MEMBER_NONE=0xFFFF)
        headers = (_location_header(0, encounter_id=99, location_name_id=0),)
        with (
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.read_code_binary",
                return_value=b"arm9",
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.conditional.resolve_map_headers",
                return_value=(headers, ("Route 1",)),
            ),
        ):
            locations, _source = _extract_encounter_locations(
                engine, platform, result, filesystem, encounter_count=1
            )

        self.assertEqual(locations, {})


class SeasonalEncounterDatasetTests(unittest.TestCase):
    def test_raises_profile_error_without_encounter_archive(self) -> None:
        profile = _profile(engine="gen5_bw", layout={})
        with self.assertRaisesRegex(
            ProfileError, "does not define an encounter archive"
        ):
            extract_seasonal_encounter_dataset(_result(profile))

    def test_success_without_grottos_swarms_or_wild_map_names(self) -> None:
        profile = _profile(engine="gen5_bw", layout={"encounters": "wild.narc"})
        result = _result(profile)
        platform = _platform({b"wild.narc": _archive(1)})
        concern = SimpleNamespace(
            parse_encounter_entry=Mock(
                side_effect=lambda data, *, map_index, archive_path: (
                    _seasonal_area(map_index, archive_path=archive_path),
                )
            ),
        )
        adapter = SimpleNamespace(encounters=concern)

        with (
            patch(
                "romwiki.pipeline.extraction.encounters.seasonal.get_platform",
                return_value=platform,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.seasonal.get_engine",
                return_value=adapter,
            ),
            patch(
                "romwiki.pipeline.extraction.encounters.seasonal.extract_reference_names",
                return_value={"pokemon_names": ["Snivy"], "name_sources": {}},
            ),
        ):
            dataset = extract_seasonal_encounter_dataset(result)

        self.assertEqual(dataset["dataset"], "wild_encounters")
        self.assertEqual(dataset["record_count"], 1)
        self.assertEqual(dataset["records"][0]["map_index"], 0)
        self.assertEqual(dataset["records"][0]["area_id"], 0)
        self.assertEqual(dataset["records"][0]["location_names"], ())
        self.assertEqual(
            dataset["source"], {"rom_sha256": "romsha256", "archive": "wild.narc"}
        )
        self.assertEqual(dataset["pokemon_names"], ["Snivy"])


class ExtractSeasonalWildMapNamesTests(unittest.TestCase):
    def test_returns_empty_when_not_configured(self) -> None:
        profile = _profile(engine="gen5_bw", layout={}, parameters={})
        result = _result(profile)
        names, source = _extract_seasonal_wild_map_names(
            result, SimpleNamespace(), _platform({}), None
        )
        self.assertEqual(names, {})
        self.assertEqual(source, {})

    def test_resolves_wild_map_names_when_configured(self) -> None:
        profile = _profile(
            engine="gen5_bw",
            layout={"map_headers": "map_headers.narc", "messages": "messages.narc"},
            parameters={"map_names_member": 7},
        )
        result = _result(profile)
        archives = {
            b"map_headers.narc": _archive(1, read=lambda index: b"map-header-data"),
            b"messages.narc": _archive(0, read=lambda index: b"messages-member-data"),
        }
        platform = _platform(archives)
        filesystem = platform.filesystem_from_image(result.image)
        engine = SimpleNamespace(
            parse_english_message_archive=Mock(return_value=("Route 1", "Route 2")),
            parse_wild_map_names=Mock(return_value={0: ["Route 1"]}),
        )

        names, source = _extract_seasonal_wild_map_names(
            result, engine, platform, filesystem
        )

        self.assertEqual(names, {0: ["Route 1"]})
        self.assertEqual(
            source,
            {
                "wild_map_names": {
                    "map_headers_archive": "map_headers.narc",
                    "map_names": {"archive": "messages.narc", "member": 7},
                }
            },
        )
        engine.parse_english_message_archive.assert_called_once_with(
            b"messages-member-data"
        )
        engine.parse_wild_map_names.assert_called_once_with(
            b"map-header-data", map_names=("Route 1", "Route 2")
        )


class ExtractHiddenGrottosTests(unittest.TestCase):
    def test_returns_empty_list_when_archive_not_configured(self) -> None:
        profile = _profile(engine="gen5_b2w2", layout={})
        result = _result(profile)
        records = _extract_hidden_grottos(
            result, SimpleNamespace(), _platform({}), None, first_area_id=0
        )
        self.assertEqual(records, [])

    def test_raises_profile_error_without_version_group(self) -> None:
        profile = _profile(
            engine="gen5_b2w2", layout={"hidden_grottos": "grottos.narc"}
        )
        result = _result(profile)
        with self.assertRaisesRegex(ProfileError, "Hidden Grotto version group"):
            _extract_hidden_grottos(
                result, SimpleNamespace(), _platform({}), None, first_area_id=0
            )

    def test_raises_invalid_rom_error_on_member_count_mismatch(self) -> None:
        profile = _profile(
            engine="gen5_b2w2",
            layout={"hidden_grottos": "grottos.narc"},
            parameters={
                "hidden_grotto_version_group": 0,
                "hidden_grotto_record_count": 3,
            },
        )
        result = _result(profile)
        platform = _platform({b"grottos.narc": _archive(2)})
        filesystem = platform.filesystem_from_image(result.image)
        with self.assertRaisesRegex(
            InvalidRomError, "Hidden Grotto archive has 2 members, expected 3"
        ):
            _extract_hidden_grottos(
                result, SimpleNamespace(), platform, filesystem, first_area_id=0
            )

    def _setup(
        self,
        *,
        grotto_count: int,
        headers: tuple[SimpleNamespace, ...],
        furniture_by_member: dict[int, list[SimpleNamespace]],
    ):
        profile = _profile(
            engine="gen5_b2w2",
            layout={
                "hidden_grottos": "grottos.narc",
                "map_headers": "map_headers.narc",
                "messages": "messages.narc",
                "overworld_objects": "overworld.narc",
            },
            parameters={
                "hidden_grotto_version_group": 0,
                "hidden_grotto_record_count": grotto_count,
                "map_names_member": 3,
                "hidden_grotto_dispatch_base": 100,
            },
        )
        result = _result(profile)
        archives = {
            b"grottos.narc": _archive(grotto_count),
            b"map_headers.narc": _archive(1, read=lambda index: b"map-header-data"),
            b"messages.narc": _archive(0, read=lambda index: b"map-names-data"),
            b"overworld.narc": _archive(len(headers)),
        }
        platform = _platform(archives)
        filesystem = platform.filesystem_from_image(result.image)

        def _furniture_for_member_data(data: bytes) -> list[SimpleNamespace]:
            member = int(data.decode().rsplit("-", 1)[1])
            return furniture_by_member.get(member, [])

        engine = SimpleNamespace(
            POKEMON_NAME_COUNT=493,
            ITEM_NAME_COUNT=468,
            ENCOUNTER_FORM_SLUGS=(),
            ENCOUNTER_COSMETIC_FORM_LABELS=(),
            parse_english_message_archive=Mock(return_value=("Route 1",)),
            parse_map_header_table=Mock(return_value=headers),
            parse_overworld_furniture=Mock(side_effect=_furniture_for_member_data),
            hidden_grotto_id_for_dispatch=hidden_grotto_id_for_dispatch,
            parse_hidden_grotto_record=Mock(
                side_effect=(
                    lambda data, *, grotto_id, archive_path, version_group, species_count, item_count, valid_forms: (
                        HiddenGrotto(  # noqa: E501
                            grotto_id=grotto_id,
                            pokemon=(),
                            visible_items=(),
                            hidden_items=(),
                            provenance=RecordProvenance("rom", archive_path, grotto_id),
                        )
                    )
                )
            ),
        )
        return result, platform, filesystem, engine

    def test_raises_invalid_rom_error_on_incomplete_dispatch_mapping(self) -> None:
        headers = (_map_header(0, overworld_file_id=0),)
        furniture = {0: [SimpleNamespace(script_used=100)]}
        result, platform, filesystem, engine = self._setup(
            grotto_count=2, headers=headers, furniture_by_member=furniture
        )
        with self.assertRaisesRegex(InvalidRomError, r"missing=\[1\]"):
            _extract_hidden_grottos(
                result, engine, platform, filesystem, first_area_id=0
            )

    def test_raises_invalid_rom_error_on_ambiguous_dispatch_mapping(self) -> None:
        headers = (
            _map_header(0, overworld_file_id=0),
            _map_header(1, overworld_file_id=1),
        )
        furniture = {
            0: [SimpleNamespace(script_used=100)],
            1: [SimpleNamespace(script_used=100)],
        }
        result, platform, filesystem, engine = self._setup(
            grotto_count=1, headers=headers, furniture_by_member=furniture
        )
        with self.assertRaisesRegex(InvalidRomError, "ambiguous"):
            _extract_hidden_grottos(
                result, engine, platform, filesystem, first_area_id=0
            )

    def test_success_builds_records_with_dispatch_resolved_location(self) -> None:
        headers = (_map_header(0, overworld_file_id=0),)
        furniture = {0: [SimpleNamespace(script_used=100)]}
        result, platform, filesystem, engine = self._setup(
            grotto_count=1, headers=headers, furniture_by_member=furniture
        )

        records = _extract_hidden_grottos(
            result, engine, platform, filesystem, first_area_id=9
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["area_id"], 9)
        self.assertEqual(record["source_type"], "hidden-grotto")
        self.assertEqual(record["grotto_id"], 0)
        self.assertEqual(
            record["location"],
            {"header_id": 0, "internal_name": "HEADER0", "name": "Location 0"},
        )


class ExtractSwarmsTests(unittest.TestCase):
    def test_returns_empty_list_when_parameters_missing(self) -> None:
        profile = _profile(engine="gen5_b2w2", parameters={})
        result = _result(profile)
        records = _extract_swarms(
            result, SimpleNamespace(), _platform({}), None, first_area_id=0
        )
        self.assertEqual(records, [])

    def test_raises_invalid_rom_error_when_table_extends_past_overlay(self) -> None:
        profile = _profile(
            engine="gen5_b2w2",
            parameters={
                "swarm_overlay_id": 12,
                "swarm_table_offset": 100,
                "swarm_record_count": 5,
            },
        )
        result = _result(profile)
        engine = SimpleNamespace(SWARM_RECORD_SIZE=8)
        overlay = SimpleNamespace(id=12)
        platform = _platform({}, overlay=Mock(return_value=(overlay, b"x" * 100)))
        with self.assertRaisesRegex(InvalidRomError, "extends past overlay 12"):
            _extract_swarms(result, engine, platform, None, first_area_id=0)

    def test_success_builds_records_with_location(self) -> None:
        profile = _profile(
            engine="gen5_b2w2",
            layout={"map_headers": "map_headers.narc", "messages": "messages.narc"},
            parameters={
                "swarm_overlay_id": 12,
                "swarm_table_offset": 0,
                "swarm_record_count": 1,
                "map_names_member": 2,
            },
        )
        result = _result(profile)
        archives = {
            b"map_headers.narc": _archive(1, read=lambda index: b"map-header-data"),
            b"messages.narc": _archive(0, read=lambda index: b"map-names-data"),
        }
        overlay = SimpleNamespace(id=12)
        platform = _platform(archives, overlay=Mock(return_value=(overlay, b"x" * 8)))
        filesystem = platform.filesystem_from_image(result.image)
        headers = (_map_header(0),)
        swarm = SwarmEncounter(
            header_id=0,
            species_id=1,
            minimum_level=5,
            maximum_level=10,
            table_offset=0,
            provenance=RecordProvenance("rom", "overlay12", 0),
        )
        engine = SimpleNamespace(
            SWARM_RECORD_SIZE=8,
            POKEMON_NAME_COUNT=649,
            parse_english_message_archive=Mock(return_value=("Route 1",)),
            parse_map_header_table=Mock(return_value=headers),
            parse_swarm_table=Mock(return_value=(swarm,)),
        )

        records = _extract_swarms(result, engine, platform, filesystem, first_area_id=7)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["area_id"], 7)
        self.assertEqual(record["source_type"], "daily-swarm")
        self.assertEqual(record["species_id"], 1)
        self.assertEqual(
            record["location"],
            {"header_id": 0, "internal_name": "HEADER0", "name": "Location 0"},
        )
        engine.parse_swarm_table.assert_called_once_with(
            b"x" * 8,
            record_count=1,
            archive_path="overlay12",
            table_offset=0,
            map_header_count=1,
            species_count=649,
        )


if __name__ == "__main__":
    unittest.main()
