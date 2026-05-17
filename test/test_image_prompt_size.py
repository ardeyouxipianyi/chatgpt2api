from __future__ import annotations

import unittest

from services.protocol.conversation import build_image_prompt


class ImagePromptSizeTests(unittest.TestCase):
    def test_known_size_adds_aspect_ratio_hint(self):
        prompt = build_image_prompt("画一张城市夜景", "16:9")

        self.assertIn("画一张城市夜景", prompt)
        self.assertIn("16:9", prompt)
        self.assertIn("横屏构图", prompt)

    def test_unknown_size_is_preserved_as_requested_ratio(self):
        prompt = build_image_prompt("画一张海报", "21:9")

        self.assertIn("画一张海报", prompt)
        self.assertIn("宽高比为 21:9", prompt)

    def test_empty_size_keeps_prompt_unchanged(self):
        self.assertEqual(build_image_prompt("画一张头像", None), "画一张头像")


if __name__ == "__main__":
    unittest.main()
