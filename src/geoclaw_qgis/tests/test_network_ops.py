from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.analysis.network_ops import TrackintelNetworkService


class TestTrackintelNetworkService(unittest.TestCase):
    def test_dry_run_without_optional_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pfs = tmp_path / "pfs.csv"
            out_dir = tmp_path / "out"
            pfs.write_text("tracked_at,latitude,longitude,user_id\n", encoding="utf-8")

            svc = TrackintelNetworkService()
            payload = svc.run_from_positionfixes_csv(
                pfs_csv=str(pfs),
                out_dir=str(out_dir),
                dry_run=True,
            )

            self.assertTrue(payload.get("success"))
            self.assertEqual(payload.get("mode"), "dry_run")
            self.assertEqual(payload.get("engine"), "trackintel")
            self.assertIn("parameters", payload)

    def test_missing_input_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svc = TrackintelNetworkService()
            with self.assertRaises(FileNotFoundError):
                svc.run_from_positionfixes_csv(
                    pfs_csv=str(Path(tmp) / "missing.csv"),
                    out_dir=str(Path(tmp) / "out"),
                    dry_run=True,
                )

    def test_real_demo_when_optional_dependencies_available(self) -> None:
        try:
            import trackintel  # noqa: F401
            import pandas  # noqa: F401
            import networkx  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("optional network dependencies are not installed")

        root = Path(__file__).resolve().parents[3]
        demo_csv = root / "data" / "examples" / "trajectory" / "trackintel_demo_pfs.csv"
        if not demo_csv.exists():
            self.skipTest("demo positionfix csv not found")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "network_out"
            svc = TrackintelNetworkService()
            payload = svc.run_from_positionfixes_csv(
                pfs_csv=str(demo_csv),
                out_dir=str(out_dir),
                staypoint_dist_threshold=120.0,
                staypoint_time_threshold=4.0,
                gap_threshold=15.0,
                activity_time_threshold=5.0,
                location_epsilon=80.0,
                location_min_samples=1,
                location_agg_level="dataset",
                dry_run=False,
            )

            self.assertTrue(payload.get("success"))
            counts = payload.get("counts", {})
            self.assertGreaterEqual(int(counts.get("od_edges", 0)), 1)
            outputs = payload.get("outputs", {})
            self.assertTrue(Path(str(outputs.get("od_edges_csv", ""))).exists())
            self.assertTrue(Path(str(outputs.get("od_nodes_csv", ""))).exists())
            self.assertTrue(Path(str(outputs.get("od_trips_csv", ""))).exists())
            self.assertTrue(Path(str(outputs.get("summary_json", ""))).exists())


if __name__ == "__main__":
    unittest.main()
