from __future__ import annotations

import re
import unittest
from pathlib import Path

from romwiki.schema.versions import CATALOG_SCHEMA_VERSION
from romwiki.sites import SUPPORTED_THEMES, SiteCatalog

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "sites" / "shared" / "overrides"
STYLES = ROOT / "sites" / "shared" / "overrides" / "assets" / "stylesheets"


def _rule_properties(css: str, selector: str) -> dict[str, str]:
    selector_start = css.index(selector)
    block_start = css.index("{", selector_start)
    block_end = css.index("}", block_start)
    return {
        name: value.strip()
        for name, value in re.findall(
            r"(--[\w-]+|[\w-]+)\s*:\s*([^;]+);",
            css[block_start + 1 : block_end],
        )
    }


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


class FrontendContractTests(unittest.TestCase):
    def test_browser_catalog_schema_matches_generated_catalogs(self) -> None:
        catalog = (
            OVERRIDES / "assets" / "javascripts" / "catalog" / "catalog.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            f"data.schema_version !== {CATALOG_SCHEMA_VERSION}",
            catalog,
        )

    def test_catalogs_hide_filters_and_sort_controls_without_choices(self) -> None:
        catalog = (
            OVERRIDES / "assets" / "javascripts" / "catalog" / "catalog.js"
        ).read_text(encoding="utf-8")

        self.assertIn(".filter(({ values }) => values.length > 1)", catalog)
        self.assertIn("if (config.sorts.length > 1)", catalog)
        self.assertIn('singleSort ? "Order" : "Direction"', catalog)

    def test_shared_theme_supports_light_dark_and_high_contrast(self) -> None:
        config = (ROOT / "sites" / "shared" / "mkdocs.base.yml").read_text(
            encoding="utf-8"
        )
        theme = (STYLES / "theme.css").read_text(encoding="utf-8")

        self.assertIn("scheme: default", config)
        self.assertIn("scheme: slate", config)
        self.assertNotIn("navigation.instant", config)
        self.assertIn("@media (forced-colors: active)", theme)

    def test_published_themes_define_applicable_light_and_dark_palettes(self) -> None:
        theme = (STYLES / "theme.css").read_text(encoding="utf-8")
        catalog = SiteCatalog.load(ROOT)
        published_themes = {site.theme for site in catalog.published()}

        self.assertLessEqual(published_themes, set(SUPPORTED_THEMES))
        self.assertIn('html[data-romwiki-theme="portal"]', theme)
        self.assertIn('body[data-md-color-scheme="slate"]', theme)

        for token in SUPPORTED_THEMES - {"portal"}:
            self.assertIn(f'html[data-romwiki-theme="{token}"]', theme)
            self.assertIn(f'.rw-game-card[data-theme="{token}"]', theme)
            self.assertIn(
                f'html[data-romwiki-theme="{token}"] '
                'body[data-md-color-scheme="slate"]',
                theme,
            )
            self.assertIn(
                'body[data-md-color-scheme="slate"] '
                f'.rw-game-card[data-theme="{token}"]',
                theme,
            )

    def test_theme_text_and_filled_accents_meet_wcag_aa_contrast(self) -> None:
        css = (STYLES / "theme.css").read_text(encoding="utf-8")
        root = _rule_properties(css, ":root")
        dark_root = {
            **root,
            **_rule_properties(css, 'body[data-md-color-scheme="slate"]'),
        }

        for token in SUPPORTED_THEMES:
            light = root
            dark = dark_root
            if token != "portal":
                light = {
                    **root,
                    **_rule_properties(
                        css,
                        f'html[data-romwiki-theme="{token}"]',
                    ),
                }
                dark = {
                    **dark_root,
                    **_rule_properties(
                        css,
                        f'html[data-romwiki-theme="{token}"] '
                        'body[data-md-color-scheme="slate"]',
                    ),
                }

            for scheme, properties in (("light", light), ("dark", dark)):
                with self.subTest(theme=token, scheme=scheme):
                    self.assertGreaterEqual(
                        _contrast(
                            properties["--rw-accent"],
                            properties["--rw-surface"],
                        ),
                        4.5,
                    )
                    self.assertGreaterEqual(
                        _contrast(
                            properties["--rw-on-accent"],
                            properties["--rw-accent-strong"],
                        ),
                        4.5,
                    )
                    self.assertGreaterEqual(
                        _contrast(
                            properties["--rw-text-muted"],
                            properties["--rw-surface"],
                        ),
                        4.5,
                    )

    def test_dark_scheme_recomputes_derived_theme_tokens_on_the_body(self) -> None:
        css = (STYLES / "theme.css").read_text(encoding="utf-8")
        dark = _rule_properties(css, 'body[data-md-color-scheme="slate"]')

        self.assertEqual(
            dark["--rw-scrollbar-thumb"],
            "rgba(var(--rw-accent-rgb), 0.44)",
        )
        self.assertEqual(
            dark["--rw-scrollbar-thumb-hover"],
            "rgba(var(--rw-accent-rgb), 0.7)",
        )
        self.assertEqual(
            dark["--md-primary-fg-color"],
            "var(--rw-accent-strong)",
        )
        self.assertEqual(dark["--md-accent-fg-color"], "var(--rw-accent)")

    def test_filled_accent_components_use_filled_theme_tokens(self) -> None:
        css = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(STYLES.glob("*.css"))
        )

        for selector in (
            ".rw-catalog__reset:hover",
            ".rw-js .rw-catalog--failed .rw-catalog__status::before",
            ".rw-record-tree__current",
            ".rw-select__match-option--selected",
            ".rw-select--multiple .rw-select__option--selected::after",
        ):
            properties = _rule_properties(css, selector)
            with self.subTest(selector=selector):
                self.assertEqual(
                    properties["background"],
                    "var(--rw-accent-strong)",
                )
                self.assertEqual(properties["color"], "var(--rw-on-accent)")

    def test_theme_and_color_preference_initialize_before_styles(self) -> None:
        template = (OVERRIDES / "main.html").read_text(encoding="utf-8")
        entrypoint = (OVERRIDES / "assets" / "javascripts" / "romwiki.js").read_text(
            encoding="utf-8"
        )

        self.assertLess(
            template.index("root.dataset.romwikiTheme"),
            template.index("theme.css"),
        )
        self.assertIn('localStorage.getItem("romwiki.color-scheme")', template)
        self.assertIn('__md_set("__palette"', template)
        self.assertIn('primary: "indigo"', template)
        self.assertIn('accent: "indigo"', template)
        self.assertIn('"romwiki.color-scheme"', entrypoint)
        self.assertIn("localStorage.setItem", entrypoint)

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

    def test_sticky_type_chart_corner_has_an_opaque_background(self) -> None:
        css = (STYLES / "records.css").read_text(encoding="utf-8")
        corner = _rule_properties(
            css,
            ".md-typeset .rw-type-chart table:not([class]) thead th:first-child",
        )

        self.assertEqual(corner["background-color"], "var(--rw-surface)")
        self.assertEqual(corner["isolation"], "isolate")
        self.assertEqual(corner["background-clip"], "border-box")
        self.assertIn(
            "thead th:first-child::before",
            css,
        )
        self.assertIn("var(--rw-surface)", css)

    def test_type_chart_uses_material_horizontal_scroll_container(self) -> None:
        records = (STYLES / "records.css").read_text(encoding="utf-8")
        theme = (STYLES / "theme.css").read_text(encoding="utf-8")
        wrapper = _rule_properties(records, ".rw-type-chart")
        scroll_wrapper = _rule_properties(
            records,
            ".rw-type-chart > .md-typeset__scrollwrap",
        )
        table_wrapper = _rule_properties(
            records,
            ".rw-type-chart .md-typeset__table",
        )
        table = _rule_properties(
            records,
            ".md-typeset .rw-type-chart table:not([class])",
        )
        sticky_column = _rule_properties(
            records,
            ".md-typeset .rw-type-chart table:not([class]) th:first-child,\n"
            ".md-typeset .rw-type-chart table:not([class]) td:first-child",
        )

        self.assertNotIn("overflow-x", wrapper)
        self.assertEqual(wrapper["margin"], "1em 0")
        self.assertEqual(scroll_wrapper["margin"], "0")
        self.assertEqual(
            scroll_wrapper["border"],
            "1px solid var(--rw-border)",
        )
        self.assertEqual(scroll_wrapper["border-radius"], ".45rem")
        self.assertEqual(
            scroll_wrapper["background-color"],
            "var(--md-default-bg-color)",
        )
        self.assertEqual(
            scroll_wrapper["overscroll-behavior-inline"],
            "contain",
        )
        self.assertEqual(table_wrapper["padding-inline"], "0")
        self.assertEqual(table["border"], "0")
        self.assertEqual(table["border-radius"], "0")
        self.assertEqual(table["overflow"], "visible")
        self.assertEqual(sticky_column["left"], "0")
        self.assertEqual(
            sticky_column["background"],
            "var(--md-default-bg-color)",
        )
        self.assertNotIn("border-left", sticky_column)
        self.assertIn(".md-typeset__scrollwrap", theme)

    def test_type_chart_effectiveness_colors_meet_wcag_aa_contrast(self) -> None:
        theme = (STYLES / "theme.css").read_text(encoding="utf-8")
        light = _rule_properties(theme, ":root")
        dark = {
            **light,
            **_rule_properties(theme, 'body[data-md-color-scheme="slate"]'),
        }

        for scheme, properties in (("light", light), ("dark", dark)):
            for state in (
                "effective",
                "effective-strong",
                "resisted",
                "resisted-strong",
                "immune",
            ):
                with self.subTest(scheme=scheme, state=state):
                    self.assertGreaterEqual(
                        _contrast(
                            properties[f"--rw-effectiveness-{state}-fg"],
                            properties[f"--rw-effectiveness-{state}-bg"],
                        ),
                        4.5,
                    )

    def test_header_game_picker_uses_a_top_layer_menu(self) -> None:
        site = (
            ROOT
            / "sites"
            / "shared"
            / "overrides"
            / "assets"
            / "javascripts"
            / "site.js"
        ).read_text(encoding="utf-8")

        self.assertIn("[data-rw-game-picker]", site)
        self.assertIn("{ popover: true }", site)

        controls = (
            ROOT
            / "sites"
            / "shared"
            / "overrides"
            / "assets"
            / "javascripts"
            / "controls.js"
        ).read_text(encoding="utf-8")
        self.assertIn('"showPopover" in HTMLElement.prototype', controls)
        self.assertIn('menu.setAttribute("popover", "auto")', controls)
        self.assertIn("menu.showPopover()", controls)


if __name__ == "__main__":
    unittest.main()
