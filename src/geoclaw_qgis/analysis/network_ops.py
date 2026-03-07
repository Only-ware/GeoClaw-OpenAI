from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class TrackintelIntegrationError(RuntimeError):
    """Raised when optional dependencies for trackintel network analysis are unavailable."""


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


@dataclass
class TrackintelNetworkService:
    """Complex mobility network analysis service powered by trackintel."""

    def _lazy_imports(self) -> tuple[Any, Any, Any]:
        try:
            import pandas as pd  # type: ignore
        except ModuleNotFoundError as exc:
            raise TrackintelIntegrationError("Missing dependency: pandas") from exc

        try:
            import networkx as nx  # type: ignore
        except ModuleNotFoundError as exc:
            raise TrackintelIntegrationError("Missing dependency: networkx") from exc

        try:
            import trackintel as ti  # type: ignore
        except ModuleNotFoundError as exc:
            raise TrackintelIntegrationError(
                "Missing dependency: trackintel. Install with `pip install trackintel` or "
                "`pip install 'geoclaw-openai[network]'`."
            ) from exc

        return pd, nx, ti

    def _optional_trackintel_version(self) -> str:
        try:
            import trackintel as ti  # type: ignore
        except ModuleNotFoundError:
            return ""
        return str(getattr(ti, "__version__", ""))

    def run_from_positionfixes_csv(
        self,
        *,
        pfs_csv: str,
        out_dir: str,
        sep: str = ",",
        index_col: str = "",
        tz: str = "UTC",
        crs: str = "EPSG:4326",
        columns_map: dict[str, str] | None = None,
        staypoint_dist_threshold: float = 100.0,
        staypoint_time_threshold: float = 5.0,
        gap_threshold: float = 15.0,
        activity_time_threshold: float = 15.0,
        location_epsilon: float = 100.0,
        location_min_samples: int = 2,
        location_agg_level: str = "user",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        src = Path(pfs_csv).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"positionfix csv not found: {src}")
        dst = Path(out_dir).expanduser().resolve()
        dst.mkdir(parents=True, exist_ok=True)

        params = {
            "pfs_csv": str(src),
            "out_dir": str(dst),
            "sep": sep,
            "index_col": index_col,
            "tz": tz,
            "crs": crs,
            "columns_map": columns_map or {},
            "staypoint_dist_threshold": staypoint_dist_threshold,
            "staypoint_time_threshold": staypoint_time_threshold,
            "gap_threshold": gap_threshold,
            "activity_time_threshold": activity_time_threshold,
            "location_epsilon": location_epsilon,
            "location_min_samples": location_min_samples,
            "location_agg_level": location_agg_level,
            "dry_run": dry_run,
        }
        if dry_run:
            return {
                "success": True,
                "mode": "dry_run",
                "engine": "trackintel",
                "trackintel_version": self._optional_trackintel_version(),
                "parameters": params,
            }

        pd, nx, ti = self._lazy_imports()

        read_kwargs: dict[str, Any] = {
            "sep": sep,
            "crs": crs,
            "tz": tz,
            "columns": columns_map or None,
        }
        if index_col:
            read_kwargs["index_col"] = index_col
        else:
            read_kwargs["index_col"] = None

        pfs = ti.io.read_positionfixes_csv(str(src), **read_kwargs)
        pfs, sp = pfs.generate_staypoints(
            method="sliding",
            dist_threshold=staypoint_dist_threshold,
            time_threshold=staypoint_time_threshold,
            gap_threshold=gap_threshold,
        )

        # Trackintel trips generation expects activity information in staypoints.
        sp = sp.create_activity_flag(method="time_threshold", time_threshold=activity_time_threshold)
        sp, locs = sp.generate_locations(
            method="dbscan",
            epsilon=location_epsilon,
            num_samples=location_min_samples,
            agg_level=location_agg_level,
        )
        pfs, tpls = pfs.generate_triplegs(staypoints=sp, method="between_staypoints", gap_threshold=gap_threshold)
        sp, tpls, trips = tpls.generate_trips(sp, gap_threshold=gap_threshold, add_geometry=False)

        # trips dataframe with resolved origin/destination location ids
        trips_df = pd.DataFrame(trips).copy()
        sp_loc = pd.Series(sp["location_id"], index=sp.index)
        trips_df["origin_location_id"] = trips_df["origin_staypoint_id"].map(sp_loc)
        trips_df["destination_location_id"] = trips_df["destination_staypoint_id"].map(sp_loc)
        trips_df["duration_min"] = (
            (trips_df["finished_at"] - trips_df["started_at"]).dt.total_seconds() / 60.0
        )

        valid_trips = trips_df.dropna(subset=["origin_location_id", "destination_location_id"]).copy()
        valid_trips = valid_trips[
            valid_trips["origin_location_id"] != valid_trips["destination_location_id"]
        ].copy()

        edge_cols = ["origin_location_id", "destination_location_id"]
        if len(valid_trips) > 0:
            edges = (
                valid_trips.groupby(edge_cols)
                .agg(
                    trip_count=("user_id", "size"),
                    user_count=("user_id", "nunique"),
                    mean_duration_min=("duration_min", "mean"),
                    median_duration_min=("duration_min", "median"),
                )
                .reset_index()
            )
        else:
            edges = pd.DataFrame(
                columns=edge_cols + ["trip_count", "user_count", "mean_duration_min", "median_duration_min"]
            )

        # Build directed OD graph for complex-network metrics.
        graph = nx.DiGraph()
        for row in edges.to_dict("records"):
            o = int(row["origin_location_id"])
            d = int(row["destination_location_id"])
            w = int(row["trip_count"])
            graph.add_edge(o, d, weight=w, user_count=int(row["user_count"]))

        node_ids = set()
        for row in edges.to_dict("records"):
            node_ids.add(int(row["origin_location_id"]))
            node_ids.add(int(row["destination_location_id"]))
        for nid in node_ids:
            if nid not in graph:
                graph.add_node(nid)

        in_strength: dict[int, float] = {
            int(n): float(sum(data.get("weight", 0) for _, _, data in graph.in_edges(n, data=True))) for n in graph.nodes
        }
        out_strength: dict[int, float] = {
            int(n): float(sum(data.get("weight", 0) for _, _, data in graph.out_edges(n, data=True))) for n in graph.nodes
        }

        degree_cent = nx.degree_centrality(graph) if graph.number_of_nodes() > 0 else {}
        inv_graph = nx.DiGraph()
        for u, v, data in graph.edges(data=True):
            weight = float(data.get("weight", 1.0))
            inv_graph.add_edge(u, v, distance=(1.0 / weight) if weight > 0 else 1.0)
        betweenness = (
            nx.betweenness_centrality(inv_graph, weight="distance")
            if inv_graph.number_of_nodes() > 0
            else {}
        )

        community_map: dict[int, int] = {}
        if graph.number_of_nodes() > 0:
            undirected = graph.to_undirected()
            try:
                communities = list(nx.community.louvain_communities(undirected, weight="weight", seed=42))
            except Exception:
                communities = list(nx.community.asyn_lpa_communities(undirected, weight="weight", seed=42))
            for cid, comm in enumerate(communities):
                for nid in comm:
                    community_map[int(nid)] = int(cid)

        visit_counts = (
            pd.DataFrame(sp[["location_id"]])
            .dropna(subset=["location_id"])
            .groupby("location_id")
            .size()
            .rename("staypoint_count")
            .to_dict()
        )

        loc_df = locs.reset_index().copy()
        if "id" in loc_df.columns:
            loc_df.rename(columns={"id": "location_id"}, inplace=True)
        center_col = "center" if "center" in loc_df.columns else (locs.geometry.name if hasattr(locs, "geometry") else "")
        if center_col and center_col in loc_df.columns and "location_id" in loc_df.columns:
            centers = loc_df[center_col]
            try:
                # GeoSeries path
                lon_vals = centers.x
                lat_vals = centers.y
            except Exception:
                # Fallback for plain Series holding point-like objects
                lon_vals = centers.apply(lambda g: _safe_float(getattr(g, "x", None)))
                lat_vals = centers.apply(lambda g: _safe_float(getattr(g, "y", None)))
            loc_df["lon"] = lon_vals
            loc_df["lat"] = lat_vals
            coord_map = (
                loc_df[["location_id", "lon", "lat"]]
                .dropna(subset=["location_id"])
                .groupby("location_id", as_index=True)[["lon", "lat"]]
                .mean(numeric_only=True)
                .to_dict("index")
            )
        else:
            coord_map = {}

        node_rows: list[dict[str, Any]] = []
        for nid in sorted(graph.nodes()):
            n = int(nid)
            coord = coord_map.get(n, {})
            node_rows.append(
                {
                    "location_id": n,
                    "in_degree": int(graph.in_degree(n)),
                    "out_degree": int(graph.out_degree(n)),
                    "in_strength": _safe_float(in_strength.get(n, 0.0)),
                    "out_strength": _safe_float(out_strength.get(n, 0.0)),
                    "total_strength": _safe_float(in_strength.get(n, 0.0) + out_strength.get(n, 0.0)),
                    "degree_centrality": _safe_float(degree_cent.get(n, 0.0)),
                    "betweenness_centrality": _safe_float(betweenness.get(n, 0.0)),
                    "community_id": _safe_int(community_map.get(n, -1)),
                    "staypoint_count": _safe_int(visit_counts.get(n)),
                    "lon": _safe_float(coord.get("lon")),
                    "lat": _safe_float(coord.get("lat")),
                }
            )
        nodes = pd.DataFrame(node_rows)

        edges_path = dst / "od_edges.csv"
        nodes_path = dst / "od_nodes.csv"
        trips_path = dst / "od_trips.csv"
        summary_path = dst / "network_summary.json"
        edges.to_csv(edges_path, index=False)
        nodes.to_csv(nodes_path, index=False)
        valid_trips.to_csv(trips_path, index=False)

        summary = {
            "success": True,
            "engine": "trackintel",
            "trackintel_version": getattr(ti, "__version__", ""),
            "input_positionfixes": str(src),
            "out_dir": str(dst),
            "parameters": params,
            "counts": {
                "positionfixes": int(len(pfs)),
                "staypoints": int(len(sp)),
                "locations": int(len(locs)),
                "triplegs": int(len(tpls)),
                "trips_total": int(len(trips_df)),
                "trips_with_locations": int(len(valid_trips)),
                "od_edges": int(len(edges)),
                "od_nodes": int(len(nodes)),
            },
            "outputs": {
                "od_edges_csv": str(edges_path),
                "od_nodes_csv": str(nodes_path),
                "od_trips_csv": str(trips_path),
                "summary_json": str(summary_path),
            },
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
