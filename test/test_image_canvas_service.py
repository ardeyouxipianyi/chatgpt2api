from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.image_canvas_service import ImageCanvasService


class ImageCanvasServiceTests(unittest.TestCase):
    def test_projects_are_isolated_by_owner(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ImageCanvasService(Path(tmp_dir) / "canvas.json")
            owner_a = {"id": "user-a", "name": "A", "role": "user"}
            owner_b = {"id": "user-b", "name": "B", "role": "user"}

            service.save_project(owner_a, {"id": "canvas-1", "title": "A 的画布", "nodes": [], "edges": []})
            service.save_project(owner_b, {"id": "canvas-1", "title": "B 的画布", "nodes": [], "edges": []})

            self.assertEqual([item["title"] for item in service.list_projects(owner_a)], ["A 的画布"])
            self.assertEqual([item["title"] for item in service.list_projects(owner_b)], ["B 的画布"])

            self.assertTrue(service.delete_project(owner_a, "canvas-1"))
            self.assertEqual(service.list_projects(owner_a), [])
            self.assertEqual([item["title"] for item in service.list_projects(owner_b)], ["B 的画布"])


if __name__ == "__main__":
    unittest.main()
