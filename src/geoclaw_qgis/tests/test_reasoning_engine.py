from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from geoclaw_qgis.profile import ensure_profile_layers, load_session_profile
from geoclaw_qgis.reasoning import build_reasoning_input, run_spatial_reasoning
from geoclaw_qgis.reasoning.input_adapter import build_reasoning_input_from_profile
from geoclaw_qgis.reasoning.schemas import ReasoningInput


class TestSpatialReasoningEngine(unittest.TestCase):
    def test_reasoning_result_schema_top_keys(self) -> None:
        payload = {
            "query": "分析武汉地铁站周边商业活跃度差异，并输出地图和摘要",
            "user_context": {
                "language": "zh-CN",
                "expertise": "GIS expert",
                "tool_preference": ["QGIS"],
                "output_preference": ["map", "summary", "workflow_trace"],
            },
            "project_context": {
                "study_area": "Wuhan",
                "default_crs": "EPSG:4547",
                "analysis_goal": "urban commercial vitality",
            },
            "datasets": [
                {
                    "id": "metro_stations",
                    "type": "vector",
                    "geometry": "point",
                    "crs": "EPSG:4326",
                    "extent": [113.7, 29.9, 115.1, 31.4],
                    "attributes": ["station_id", "name", "line"],
                },
                {
                    "id": "poi_commerce",
                    "type": "vector",
                    "geometry": "point",
                    "crs": "EPSG:4326",
                    "extent": [113.8, 29.95, 115.0, 31.3],
                    "time_range": "2025",
                    "attributes": ["poi_id", "category", "name"],
                },
            ],
            "planner_hints": {
                "candidate_task_type": "proximity_analysis",
                "candidate_methods": ["buffer", "spatial_join"],
            },
            "system_policy": {
                "readonly_inputs": True,
                "require_output_workspace": True,
                "allow_unregistered_tools": False,
            },
        }

        input_data = ReasoningInput.from_dict(payload)
        result = run_spatial_reasoning(input_data)
        data = result.to_dict()

        self.assertEqual(data["task_profile"]["task_type"], "proximity_analysis")
        self.assertIn("workflow_plan", data)
        self.assertIn("validation", data)
        self.assertIn("provenance", data)
        self.assertIn("execution_plan", data)
        self.assertIn("steps", data["workflow_plan"])
        self.assertIn("required_preconditions", data["validation"])
        self.assertIn("reasoning_mode", data["reasoning_summary"])
        self.assertIn("uncertainty_score", data["reasoning_summary"])
        self.assertIn("sensitivity_hints", data["reasoning_summary"])

    def test_distance_task_requires_reprojection_precondition(self) -> None:
        input_data = build_reasoning_input(
            query="计算站点周边500米范围内POI数量",
            datasets=[
                {"id": "stations", "type": "vector", "geometry": "point", "crs": "EPSG:4326"},
                {"id": "poi", "type": "vector", "geometry": "point", "crs": "EPSG:4326"},
            ],
            planner_hints={"candidate_task_type": "proximity_analysis"},
            project_context={"default_crs": "EPSG:4547"},
        )
        result = run_spatial_reasoning(input_data).to_dict()

        preconditions = result["workflow_plan"]["preconditions"]
        self.assertGreaterEqual(len(preconditions), 1)
        self.assertEqual(preconditions[0]["action"], "reproject_layer")
        self.assertEqual(preconditions[0]["to_crs"], "EPSG:4547")
        self.assertIn(result["validation"]["status"], {"pass", "pass_with_warnings"})
        self.assertIn("reproject_to_metric_crs", result["validation"]["required_preconditions"])
        self.assertIn("buffer_operation_moved_after_reprojection", result["validation"]["revisions_applied"])
        self.assertIn("radii_m", result["workflow_plan"]["steps"][0]["parameters"])
        self.assertIn(500, result["workflow_plan"]["steps"][0]["parameters"]["radii_m"])
        self.assertTrue(bool(result["reasoning_summary"]["sensitivity_hints"]))

    def test_change_detection_requires_multiple_time_slices(self) -> None:
        input_data = build_reasoning_input(
            query="比较两期建设用地变化并检测扩张趋势",
            datasets=[
                {"id": "land_2025", "type": "vector", "geometry": "polygon", "crs": "EPSG:4547", "time_range": "2025"}
            ],
            planner_hints={"candidate_task_type": "change_detection"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertEqual(result["validation"]["status"], "fail")
        self.assertTrue(any(x["code"] == "TEMPORAL_SLICES_REQUIRED" for x in result["validation"]["blocking_errors"]))
        self.assertIn("attach_at_least_two_time_slices", result["validation"]["required_preconditions"])
        self.assertEqual(result["workflow_plan"]["steps"][0]["parameters"].get("comparison_mode"), "pairwise_change")
        self.assertFalse(result["execution_plan"]["safe_to_execute"])
        self.assertEqual(result["execution_plan"]["route_target"], "blocked")

    def test_trajectory_task_requires_trajectory_data(self) -> None:
        input_data = build_reasoning_input(
            query="做OD流动分析与轨迹分段",
            datasets=[{"id": "pois", "type": "vector", "geometry": "point", "crs": "EPSG:4326"}],
            planner_hints={"candidate_task_type": "trajectory_analysis"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertEqual(result["validation"]["status"], "fail")
        self.assertTrue(any(x["code"] == "TRAJECTORY_DATA_REQUIRED" for x in result["validation"]["blocking_errors"]))
        self.assertIn("attach_trajectory_or_network_dataset", result["validation"]["required_preconditions"])
        self.assertEqual(result["workflow_plan"]["steps"][0]["parameters"].get("min_trip_points"), 2)
        self.assertFalse(result["execution_plan"]["safe_to_execute"])

    def test_trajectory_task_with_valid_data_routes_network(self) -> None:
        input_data = build_reasoning_input(
            query="做OD流动分析与轨迹分段",
            datasets=[
                {
                    "id": "traj",
                    "path": "data/examples/trajectory/trackintel_demo_pfs.csv",
                    "type": "trajectory",
                    "geometry": "point",
                    "crs": "EPSG:4326",
                }
            ],
            planner_hints={"candidate_task_type": "trajectory_analysis"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertIn(result["validation"]["status"], {"pass", "pass_with_warnings"})
        self.assertTrue(result["execution_plan"]["safe_to_execute"])
        self.assertEqual(result["execution_plan"]["route_target"], "network")
        self.assertEqual(result["execution_plan"]["command"][0], "network")
        self.assertIn("--pfs-csv", result["execution_plan"]["command"])

    def test_proximity_task_routes_run_location_analysis(self) -> None:
        input_data = build_reasoning_input(
            query="做可达性和邻近分析",
            datasets=[
                {"id": "a", "type": "vector", "geometry": "point", "crs": "EPSG:4547"},
                {"id": "b", "type": "vector", "geometry": "point", "crs": "EPSG:4547"},
            ],
            planner_hints={"candidate_task_type": "proximity_analysis"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertEqual(result["execution_plan"]["route_target"], "run")
        self.assertEqual(result["execution_plan"]["command"][:3], ["run", "--case", "location_analysis"])
        self.assertEqual(result["reasoning_summary"]["reasoning_mode"], "exploratory")

    def test_site_selection_mall_prefers_qgis_skill_route(self) -> None:
        input_data = build_reasoning_input(
            query="做一个武汉商场选址分析并输出候选点",
            datasets=[
                {"id": "candidate", "type": "vector", "geometry": "point", "crs": "EPSG:4547"},
                {"id": "population", "type": "vector", "geometry": "polygon", "crs": "EPSG:4547"},
            ],
            planner_hints={"candidate_task_type": "site_selection"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertEqual(result["execution_plan"]["route_target"], "skill")
        self.assertTrue(result["execution_plan"]["safe_to_execute"])
        self.assertEqual(result["execution_plan"]["command"][:4], ["skill", "--", "--skill", "mall_site_selection_qgis"])
        self.assertIn("criteria", result["workflow_plan"]["steps"][0]["parameters"])
        self.assertIn("weights", result["workflow_plan"]["steps"][0]["parameters"])

    def test_overlay_guards_are_recorded_in_revisions(self) -> None:
        input_data = build_reasoning_input(
            query="做两个图层的面积叠加分析",
            datasets=[
                {
                    "id": "a",
                    "type": "vector",
                    "geometry": "polygon",
                    "crs": "EPSG:4326",
                    "extent": [113.0, 30.0, 113.2, 30.2],
                },
                {
                    "id": "b",
                    "type": "vector",
                    "geometry": "polygon",
                    "crs": "EPSG:4547",
                    "extent": [114.0, 31.0, 114.2, 31.2],
                },
            ],
            planner_hints={"candidate_task_type": "spatial_comparison"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertIn("unify_crs_before_overlay", result["validation"]["required_preconditions"])
        self.assertIn("ensure_dataset_extent_overlap", result["validation"]["required_preconditions"])
        self.assertIn("overlay_operations_guarded_by_crs_unification", result["validation"]["revisions_applied"])
        self.assertIn("overlay_operations_guarded_by_extent_overlap_check", result["validation"]["revisions_applied"])
        pre_actions = [x["action"] for x in result["workflow_plan"]["preconditions"]]
        self.assertIn("unify_crs", pre_actions)
        self.assertIn("validate_extent_overlap", pre_actions)

    def test_causal_intent_adds_guardrails_and_high_uncertainty(self) -> None:
        input_data = build_reasoning_input(
            query="分析地铁开通是否导致周边房价上涨，做因果推断",
            datasets=[
                {"id": "metro_open", "type": "vector", "geometry": "point", "crs": "EPSG:4326"},
            ],
            planner_hints={"candidate_task_type": "spatial_comparison"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertEqual(result["reasoning_summary"]["reasoning_mode"], "causal_inference")
        self.assertIn("provide_identification_strategy", result["validation"]["required_preconditions"])
        self.assertTrue(any(x["code"] == "CAUSAL_GUARDRAIL_REQUIRED" for x in result["validation"]["warnings"]))
        self.assertIn(result["reasoning_summary"]["uncertainty_level"], {"medium", "high"})
        self.assertGreater(result["reasoning_summary"]["uncertainty_score"], 0.5)

    def test_maup_keywords_emit_scale_warning_and_sensitivity(self) -> None:
        input_data = build_reasoning_input(
            query="比较不同尺度单元下商业分布差异，注意MAUP影响",
            datasets=[
                {"id": "grid1", "type": "vector", "geometry": "polygon", "crs": "EPSG:4547"},
                {"id": "grid2", "type": "vector", "geometry": "polygon", "crs": "EPSG:4547"},
            ],
            planner_hints={"candidate_task_type": "spatial_comparison"},
        )
        result = run_spatial_reasoning(input_data).to_dict()
        self.assertTrue(any(x["message"] == "maup_or_scale_effects_should_be_reported" for x in result["validation"]["warnings"]))
        self.assertIn("spatial_scale_sensitivity", result["reasoning_summary"]["sensitivity_hints"])
        self.assertTrue(any(("maup" in x.lower()) or ("scale" in x.lower()) for x in result["reasoning_summary"]["limitations"]))

    def test_profile_adapter_builds_reasoning_input(self) -> None:
        old_env = dict(os.environ)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                os.environ["GEOCLAW_OPENAI_HOME"] = str(root / "home")
                ensure_profile_layers(root)
                session = load_session_profile(root, force_reload=True)

                input_data = build_reasoning_input_from_profile(
                    query="做一个学校AED选址分析",
                    session=session,
                    datasets=[
                        {"id": "schools", "type": "vector", "geometry": "point", "crs": "EPSG:4326"}
                    ],
                )
                self.assertEqual(input_data.user_context.expertise, session.user.role)
                self.assertTrue(input_data.system_policy.readonly_inputs)
        finally:
            os.environ.clear()
            os.environ.update(old_env)


if __name__ == "__main__":
    unittest.main()
