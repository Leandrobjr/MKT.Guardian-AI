"""Testes dos templates de composição por canal."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from composition_templates import get_composition_template, list_composition_templates


class TestCompositionTemplates(unittest.TestCase):
    def test_cada_template_define_layout_completo(self):
        templates = list_composition_templates()
        self.assertEqual(
            {template.preset_id for template in templates},
            {"feed_quadrado", "meta_reels", "shorts_urgente"},
        )
        for template in templates:
            self.assertEqual(len(template.safe_area), 4)
            self.assertEqual(len(template.card_regions), 3)
            self.assertTrue(template.logo_anchor)
            self.assertTrue(template.animation)
            self.assertIn("cta", template.colors)
            safe_bottom = template.safe_area[3]
            self.assertTrue(
                all(region[3] <= 1 - safe_bottom for region in template.card_regions)
            )

    def test_fallback_e_template_do_feed(self):
        self.assertEqual(
            get_composition_template("desconhecido").preset_id,
            "meta_reels",
        )
        self.assertEqual(
            get_composition_template("feed_quadrado").template_id,
            "guardian_feed_quadrado_v1",
        )


if __name__ == "__main__":
    unittest.main()
