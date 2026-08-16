from __future__ import annotations

import unittest

from romwiki.renderers.mkdocs.comparisons import (
    _format_ability_pokemon_change,
    _format_evolutions,
    _format_level_up_moves,
    _format_machine_compatibility,
    _format_trainer_location_change,
)


def _pokemon(member: int, slots: list[int]) -> dict:
    return {"member": member, "name": "Bulbasaur", "slug": "bulbasaur", "slots": slots}


class FormatAbilityPokemonChangeTests(unittest.TestCase):
    def test_reports_a_changed_slot(self) -> None:
        before = [_pokemon(1, [1])]
        after = [_pokemon(1, [2])]

        result = _format_ability_pokemon_change(before, after, "", None)

        self.assertIn("1 ability slot change", result)
        self.assertIn("Slot 1", result)
        self.assertIn("Slot 2", result)

    def test_reports_a_removed_pokemon(self) -> None:
        before = [_pokemon(1, [1])]

        result = _format_ability_pokemon_change(before, [], "", None)

        self.assertIn("1 Pokémon that lost this ability", result)

    def test_reports_an_added_pokemon(self) -> None:
        after = [_pokemon(1, [1])]

        result = _format_ability_pokemon_change([], after, "", None)

        self.assertIn("1 Pokémon that gained this ability", result)

    def test_treats_a_reordered_but_otherwise_identical_list_as_order_changed(
        self,
    ) -> None:
        before = [_pokemon(1, [1]), _pokemon(2, [1])]
        after = [_pokemon(2, [1]), _pokemon(1, [1])]

        self.assertEqual(
            _format_ability_pokemon_change(before, after, "", None), "Order changed"
        )


def _trainer_location(header_id: int, x: int, z: int) -> dict:
    return {
        "header_id": header_id,
        "object_index": 0,
        "event_file_id": None,
        "name": "Route 1",
        "x": x,
        "z": z,
    }


class FormatTrainerLocationChangeTests(unittest.TestCase):
    def test_reports_a_position_change(self) -> None:
        before = [_trainer_location(6, 10, 20)]
        after = [_trainer_location(6, 15, 25)]

        result = _format_trainer_location_change(before, after, "", None)

        self.assertIn("1 position change", result)
        self.assertIn("(10, 20)", result)
        self.assertIn("(15, 25)", result)

    def test_reports_a_removed_location(self) -> None:
        before = [_trainer_location(6, 10, 20)]

        result = _format_trainer_location_change(before, [], "", None)

        self.assertIn("1 location removed", result)

    def test_reports_an_added_location(self) -> None:
        after = [_trainer_location(6, 10, 20)]

        result = _format_trainer_location_change([], after, "", None)

        self.assertIn("1 location added", result)


def _level_up_move(level: int, move_id: int = 1) -> dict:
    return {"level": level, "move": {"id": move_id, "name": "Tackle", "slug": "tackle"}}


class FormatLevelUpMovesTests(unittest.TestCase):
    def test_reports_a_level_change(self) -> None:
        before = [_level_up_move(5)]
        after = [_level_up_move(8)]

        result = _format_level_up_moves(before, after, "", None)

        self.assertIn("1 level change", result)
        self.assertIn("Lv. 5", result)
        self.assertIn("Lv. 8", result)

    def test_reports_a_removed_move(self) -> None:
        before = [_level_up_move(5)]

        result = _format_level_up_moves(before, [], "", None)

        self.assertIn("1 move removed", result)
        self.assertIn("Not learned", result)

    def test_reports_an_added_move(self) -> None:
        after = [_level_up_move(5)]

        result = _format_level_up_moves([], after, "", None)

        self.assertIn("1 move added", result)


def _evolution(target_id: int, level: int) -> dict:
    return {
        "target": {"id": target_id, "name": "Ivysaur", "slug": "ivysaur"},
        "method": {"name": "level-up"},
        "parameter_data": {"kind": "level", "value": level},
    }


class FormatEvolutionsTests(unittest.TestCase):
    def test_reports_a_condition_change(self) -> None:
        before = [_evolution(2, 16)]
        after = [_evolution(2, 20)]

        result = _format_evolutions(before, after, "", None)

        self.assertIn("1 evolution change", result)

    def test_reports_a_removed_evolution(self) -> None:
        before = [_evolution(2, 16)]

        result = _format_evolutions(before, [], "", None)

        self.assertIn("1 evolution removed", result)

    def test_reports_an_added_evolution(self) -> None:
        after = [_evolution(2, 16)]

        result = _format_evolutions([], after, "", None)

        self.assertIn("1 evolution added", result)


def _machine(machine_id: int) -> dict:
    return {
        "id": machine_id,
        "name": "TM01",
        "move": {"id": 5, "name": "Tackle", "slug": "tackle"},
    }


class FormatMachineCompatibilityTests(unittest.TestCase):
    def test_reports_a_machine_that_became_incompatible(self) -> None:
        before = [_machine(1)]

        result = _format_machine_compatibility(before, [], "", None)

        self.assertIn("1 change", result)
        self.assertIn("Compatible", result)
        self.assertIn("Not compatible", result)

    def test_reports_a_machine_that_became_compatible(self) -> None:
        after = [_machine(1)]

        result = _format_machine_compatibility([], after, "", None)

        self.assertIn("1 change", result)

    def test_reports_no_changes_for_identical_compatibility(self) -> None:
        before = [_machine(1)]
        after = [_machine(1)]

        self.assertEqual(
            _format_machine_compatibility(before, after, "", None), "No changes"
        )


if __name__ == "__main__":
    unittest.main()
