from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLES = ROOT / "sites" / "shared" / "overrides" / "assets" / "stylesheets"


class FrontendContractTests(unittest.TestCase):
    def test_shared_theme_supports_light_dark_and_high_contrast(self) -> None:
        config = (ROOT / "sites" / "shared" / "mkdocs.base.yml").read_text(
            encoding="utf-8"
        )
        theme = (STYLES / "theme.css").read_text(encoding="utf-8")

        self.assertIn("scheme: default", config)
        self.assertIn("scheme: slate", config)
        self.assertIn("@media (forced-colors: active)", theme)

    def test_interactive_and_dense_components_keep_accessibility_states(self) -> None:
        css = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(STYLES.glob("*.css"))
        )

        self.assertIn(":focus-visible", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("@media (max-width: 44rem)", css)
        self.assertIn(".rw-party-card__move-meta", css)
        self.assertIn("justify-self: end", css)
        self.assertIn(".rw-party-card__stats caption", css)


if __name__ == "__main__":
    unittest.main()
