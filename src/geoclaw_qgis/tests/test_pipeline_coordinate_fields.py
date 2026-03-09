from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class TestPipelineCoordinateFields(unittest.TestCase):
    def test_site_selection_outputs_lon_lat_fields(self) -> None:
        text = (ROOT / "pipelines/cases/site_selection.yaml").read_text(encoding="utf-8")
        self.assertIn("TARGET_CRS: EPSG:4326", text)
        self.assertIn("FIELD_NAME: LONGITUDE", text)
        self.assertIn("FIELD_NAME: LATITUDE", text)
        self.assertIn("FIELDS: SITE_RANK;SITE_SCORE;SITE_CLASS;LONGITUDE;LATITUDE;", text)

    def test_mall_selection_outputs_lon_lat_fields(self) -> None:
        text = (ROOT / "pipelines/cases/mall_site_selection_qgis.yaml").read_text(encoding="utf-8")
        self.assertIn("TARGET_CRS: EPSG:4326", text)
        self.assertIn("FIELD_NAME: LONGITUDE", text)
        self.assertIn("FIELD_NAME: LATITUDE", text)
        self.assertIn("FIELDS: MALL_RANK;MALL_SCORE;MALL_CLASS;LONGITUDE;LATITUDE;", text)


if __name__ == "__main__":
    unittest.main()
