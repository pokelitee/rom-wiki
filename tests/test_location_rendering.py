from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from romwiki.renderers.mkdocs import render_location_pages


class LocationRenderingTests(unittest.TestCase):
    def test_renders_navigation_encounters_and_trainers(self) -> None:
        record = {
            "header_id": 45,
            "internal_name": "C03",
            "location_name_id": 7,
            "name": "Oreburgh City",
            "matrix_id": 0,
            "event_file_id": 42,
            "encounter_id": 3,
            "trainers": [
                {
                    "trainer_id": 246,
                    "name": "Roark",
                    "class_name": "Leader",
                    "source": "map-script",
                }
            ],
            "warps": [
                {
                    "index": 0,
                    "x": 10,
                    "z": 20,
                    "destination_header_id": 47,
                    "destination_warp_id": 0,
                    "destination_name": "Oreburgh City",
                    "destination_internal_name": "C03GYM0101",
                    "destination_warp_exists": True,
                    "dynamic": False,
                }
            ],
            "connections": [
                {
                    "destination_header_id": 344,
                    "destination_name": "Route 203",
                    "destination_internal_name": "R203",
                    "directions": ["west"],
                }
            ],
        }
        dataset = {"records": [record]}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            count = render_location_pages(dataset, output)
            page = (output / "header-045.md").read_text(encoding="utf-8")

        self.assertEqual(count, 1)
        self.assertIn("../encounters/area-003.md", page)
        self.assertIn("../trainers/trainer-0246.md", page)
        self.assertIn("./header-047.md", page)
        self.assertIn("./header-344.md", page)


if __name__ == "__main__":
    unittest.main()
