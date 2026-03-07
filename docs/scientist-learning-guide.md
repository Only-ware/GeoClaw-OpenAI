# GeoClaw-OpenAI 科研学习手册（v1.1.0）

适用对象：科研人员、研究生、GIS 初学者  
项目归属：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 你可以完成什么

- 按城市名或 bbox 快速获取 OSM 数据并开展空间分析
- 同时完成矢量与栅格分析流程
- 用统一 CLI 运行内置案例（区位分析、选址分析）
- 用灵活参数定义方式（命令行、JSON、YAML）运行单算法或 pipeline

## 2. 最小可运行路径（初学者）

```bash
# 1) 安装与初始化
bash scripts/install_geoclaw_openai.sh
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh

# 2) 直接运行（城市名）
geoclaw-openai run --case native_cases --city "武汉市"
```

输出重点：

- `data/outputs/<tag>_location/grid_location.gpkg`
- `data/outputs/<tag>_site/site_candidates.gpkg`

## 3. 三种输入源模式

`geoclaw-openai run` 支持 3 种输入方式（互斥）：

1. `--city`：按城市名地理编码并下载数据  
   示例：`geoclaw-openai run --case location_analysis --city "武汉市"`
2. `--bbox`：按边界框下载数据  
   示例：`geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"`
3. `--data-dir`：直接使用本地数据目录  
   示例：`geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download`

本地目录必须包含：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

## 4. 栅格与矢量 demo（开箱即用）

```bash
bash scripts/run_beginner_demos.sh
```

会自动运行两个教学 pipeline：

- 矢量：`pipelines/examples/vector_basics.yaml`
- 栅格：`pipelines/examples/raster_basics.yaml`

核心产物：

- 矢量结果：`data/outputs/demo_vector/roads_service_corridor.gpkg`
- 栅格统计结果：`data/outputs/demo_raster/grid_heat_norm.gpkg`

## 5. 参数定义的灵活方式（重点）

## 5.1 Pipeline 变量覆盖

`run_qgis_pipeline.py` 支持三种覆盖方式：

- `--set KEY=VALUE`（字符串）
- `--set-json KEY=JSON`（类型化 JSON）
- `--vars-file`（JSON/YAML 文件覆盖）

示例（文件覆盖）：

```bash
python3 scripts/run_qgis_pipeline.py \
  --config pipelines/examples/vector_basics.yaml \
  --vars-file configs/examples/vars_override_demo.yaml
```

示例（JSON 覆盖）：

```bash
python3 scripts/run_qgis_pipeline.py \
  --config pipelines/examples/raster_basics.yaml \
  --set raw_dir=data/raw/wuhan_osm \
  --set out_dir=data/outputs/demo_raster_json \
  --set-json grid_spacing_m=1500 \
  --set-json heat_radius_m=3200
```

## 5.2 单算法灵活运行（operator）

```bash
# 方式 A：命令行参数
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param DISTANCE=1000 \
  --param DISSOLVE=1 \
  --param OUTPUT=data/outputs/demo_operator/hosp_buffer.gpkg

# 方式 B：参数文件
geoclaw-openai operator \
  --algorithm native:buffer \
  --params-file configs/examples/operator_buffer_params.yaml
```

## 6. Python API（研究代码中调用）

```python
from geoclaw_qgis.providers import QgisProcessRunner
from geoclaw_qgis.analysis import VectorAnalysisService, RasterAnalysisService

runner = QgisProcessRunner("/Applications/QGIS.app/Contents/MacOS/bin/qgis_process")
vec = VectorAnalysisService(runner)
ras = RasterAnalysisService(runner)

result = vec.buffer(
    input_path="data/raw/wuhan_osm/hospitals.geojson",
    distance=1000,
    output_path="data/outputs/demo_api/hosp_buffer.gpkg",
    DISSOLVE=1,
)
print(result.success, result.outputs)
```

## 7. 科研复现建议

- 将每次输出目录按实验编号区分（如 `exp_20260307_a`）
- 保存 `pipeline_report.json`（含版本与归属信息）
- 固定 bbox、投影、权重参数后再做对比实验
- 对外发布结果时注明数据抓取时间与来源（OSM/Overpass）

## 8. 常见问题

1. `qgis_process not found`  
   处理：在 `onboard` 时设置 `--qgis-process` 或写入 `GEOCLAW_OPENAI_QGIS_PROCESS`。
2. 本地目录运行失败提示缺少文件  
   处理：补齐四个 GeoJSON 文件或改用 `--city/--bbox` 自动下载。
3. AI 401 报错  
   处理：检查 `GEOCLAW_OPENAI_API_KEY`，这不影响核心 GIS 流程运行。
