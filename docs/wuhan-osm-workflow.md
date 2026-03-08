# 武汉 OSM 测试流程（v3.0.0）

本文档用于复现实验：下载数据 -> 空间分析 -> 出图。

## 1) 数据准备

方式 A：直接下载

```bash
python3 scripts/download_osm_wuhan.py --bbox 30.50,114.20,30.66,114.45 --timeout 120
```

方式 B：统一 CLI（推荐）

```bash
geoclaw-openai run --case location_analysis --city "武汉市"
```

原始数据目录：`data/raw/wuhan_osm/`

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

## 2) 复杂空间分析

```bash
# 传统脚本入口
bash scripts/run_wuhan_case.sh

# 或统一 CLI
geoclaw-openai run --case wuhan_advanced --bbox "30.50,114.20,30.66,114.45" --with-maps
```

关键产物：`data/outputs/<tag>_analysis/grid_clustered.gpkg`

## 3) 批量出图

```bash
bash scripts/export_wuhan_map.sh
```

输出目录：`data/outputs/<tag>_analysis/maps/`

- `geoclaw_index.png`
- `road_intensity.png`
- `accessibility.png`
- `hotspot.png`

## 4) 成果复核

```bash
ogrinfo -so -al data/outputs/wuhan_analysis/grid_clustered.gpkg
```

建议重点检查字段：

- 统计字段：`RD_LEN_M`、`RD_CNT`、`hosp2km_pc`、`water500m_pc`
- 归一化字段：`RD_NORM`、`HOSP_NORM`、`HEAT_NORM`、`ACCESS_NORM`
- 综合字段：`GEOCLAW_IDX`

## 5) 安全策略说明

GeoClaw v3.0.0 默认启用输出安全控制：

- 输出必须在 `data/outputs`
- 禁止覆盖输入文件

因此请不要把输出路径设置到 `data/raw`。
