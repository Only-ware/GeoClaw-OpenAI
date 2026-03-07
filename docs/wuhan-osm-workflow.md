# 武汉 OSM 测试流程（YAML Pipeline + 复杂分析 + 批量出图）

## 1) 下载测试数据

```bash
python3 scripts/download_osm_wuhan.py --bbox 30.50,114.20,30.66,114.45 --timeout 120
```

输出目录：`data/raw/wuhan_osm/`

- `roads.geojson` 道路线
- `water.geojson` 水系/水体（线或面）
- `hospitals.geojson` 医院/诊所点
- `study_area.geojson` 研究范围

## 2) 执行 YAML Pipeline（复杂空间分析）

```bash
bash scripts/run_wuhan_geoclaw_pipeline.sh pipelines/wuhan_geoclaw.yaml
```

核心分析步骤：

1. 全量重投影到 `EPSG:32650`
2. 创建 2km 网格
3. 道路长度/数量统计
4. 医院 2km 覆盖率
5. 水体 500m 覆盖率
6. 医疗热点核密度 + zonal mean
7. 最近医疗设施距离
8. 多指标归一化
9. 生成综合指数 `GEOCLAW_IDX`
10. KMeans 聚类分区

关键成果：`data/outputs/wuhan_analysis/grid_clustered.gpkg`

## 3) 批量出图（模板化）

```bash
bash scripts/export_wuhan_map.sh
```

输出目录：`data/outputs/wuhan_analysis/maps/`

- `geoclaw_index.png`
- `road_intensity.png`
- `accessibility.png`
- `hotspot.png`

说明：在当前 QGIS/GDAL 组合下，导图时可能输出一条 PNG driver 的 `ERROR 6` 日志，但命令返回码为 0，图片会正常产出。

## 4) 一键执行

```bash
bash scripts/run_wuhan_case.sh
```

## 5) 复核

```bash
ogrinfo -so -al data/outputs/wuhan_analysis/grid_clustered.gpkg
```

重点字段：

- 原始统计：`RD_LEN_M`、`RD_CNT`、`hosp2km_pc`、`water500m_pc`、`HM_mean`、`NN_HubDist`
- 归一化字段：`RD_NORM`、`HOSP_NORM`、`WATER_NORM`、`HEAT_NORM`、`ACCESS_NORM`
- 综合评分：`GEOCLAW_IDX`
- 分区字段：`ZONE_ID`、`ZONE_SIZE`
