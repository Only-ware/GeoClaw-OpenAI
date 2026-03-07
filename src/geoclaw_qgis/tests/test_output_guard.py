from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.security import OutputSecurityError, fixed_output_root, validate_output_targets


class TestOutputGuard(unittest.TestCase):
    def test_accepts_output_under_fixed_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = {
                "INPUT": "data/raw/wuhan_osm/hospitals.geojson",
                "OUTPUT": "data/outputs/demo/safe.gpkg",
            }
            out_map = validate_output_targets(params, workspace_root=root)
            self.assertIn("OUTPUT", out_map)
            self.assertTrue(str(out_map["OUTPUT"]).startswith(str(fixed_output_root(root))))

    def test_rejects_output_outside_fixed_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = {
                "INPUT": "data/raw/wuhan_osm/hospitals.geojson",
                "OUTPUT": "data/raw/wuhan_osm/unsafe.gpkg",
            }
            with self.assertRaises(OutputSecurityError):
                validate_output_targets(params, workspace_root=root)

    def test_rejects_inplace_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            params = {
                "INPUT": "data/raw/wuhan_osm/hospitals.geojson",
                "OUTPUT": "data/raw/wuhan_osm/hospitals.geojson",
            }
            with self.assertRaises(OutputSecurityError):
                validate_output_targets(params, workspace_root=root)


if __name__ == "__main__":
    unittest.main()
