from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.reasoning.data_catalog_adapter import (
    check_extent_overlaps,
    dataset_spec_from_path,
    discover_datasets_from_dir,
)


class TestReasoningDataCatalogAdapter(unittest.TestCase):
    def test_discover_geojson_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gj = root / "poi.geojson"
            hidden = root / "._poi.geojson"
            gj.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [114.3, 30.5]},
                                "properties": {"id": 1, "name": "A"},
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [114.4, 30.6]},
                                "properties": {"id": 2, "name": "B"},
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            hidden.write_text("{}", encoding="utf-8")

            one = dataset_spec_from_path(gj)
            self.assertEqual(one["type"], "vector")
            self.assertEqual(one["geometry"], "point")
            self.assertTrue(bool(one["extent"]))

            all_specs = discover_datasets_from_dir(root)
            self.assertEqual(len(all_specs), 1)
            self.assertEqual(all_specs[0]["id"], "poi")

    def test_extent_overlap_check(self) -> None:
        self.assertTrue(
            check_extent_overlaps(
                [
                    {"id": "a", "extent": [0, 0, 1, 1]},
                    {"id": "b", "extent": [0.5, 0.5, 1.5, 1.5]},
                ]
            )
        )
        self.assertFalse(
            check_extent_overlaps(
                [
                    {"id": "a", "extent": [0, 0, 1, 1]},
                    {"id": "b", "extent": [2, 2, 3, 3]},
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
