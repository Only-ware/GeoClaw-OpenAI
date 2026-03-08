# GeoClaw-OpenAI 科研学习手册（v3.0.0）

适用对象：科研人员、研究生、GIS 初学者  
项目归属：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 你可以做什么

- 用城市名、bbox 或本地数据目录快速开展区位/选址分析
- 运行矢量与栅格教学 demo
- 用自然语言驱动 CLI（预览或直接执行）
- 用 memory 做任务复盘、归档和历史检索
- 用 TrackIntel 进行轨迹 OD 网络分析

## 2. 最小可运行路径

```bash
bash scripts/install_geoclaw_openai.sh
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
geoclaw-openai profile init

geoclaw-openai run --case native_cases --city "武汉市"
```

默认输出在 `data/outputs/` 下。

## 2.1 Soul/User 个性化层

```bash
geoclaw-openai profile show
```

- `soul.md`：系统级原则与执行边界（如不覆盖输入、优先可复现流程）。
- `user.md`：用户长期偏好（语言风格、工具偏好、输出习惯）。
- 两者在会话初始化自动加载，并影响 NL 规划、路由、报告与复盘建议。

## 3. 三种输入方式（互斥）

```bash
# 城市名
geoclaw-openai run --case location_analysis --city "武汉市"

# bbox
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 本地目录
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download
```

本地目录必须包含：

- `roads.geojson`
- `water.geojson`
- `hospitals.geojson`
- `study_area.geojson`

## 4. 初学者 demo

```bash
# 矢量 + 栅格教学示例
bash scripts/run_beginner_demos.sh
```

常见结果：

- `data/outputs/demo_vector/roads_service_corridor.gpkg`
- `data/outputs/demo_raster/grid_heat_norm.gpkg`

## 5. 单算法灵活参数

```bash
# 命令行参数
geoclaw-openai operator \
  --algorithm native:buffer \
  --param INPUT=data/raw/wuhan_osm/hospitals.geojson \
  --param DISTANCE=1000 \
  --param OUTPUT=data/outputs/demo_operator/hosp_buffer.gpkg

# 参数文件
geoclaw-openai operator \
  --algorithm native:buffer \
  --params-file configs/examples/operator_buffer_params.yaml
```

## 6. 自然语言入口

```bash
# 预览
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 执行
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

当前支持解析到：`run`、`operator`、`network`、`skill`、`memory`、`update`。

## 7. AI Provider 与上下文压缩

支持 provider：

- `openai`
- `qwen`
- `gemini`

切换示例：

```bash
geoclaw-openai config set --ai-provider openai --ai-model gpt-5.4
geoclaw-openai config set --ai-provider qwen --ai-model qwen3-max
geoclaw-openai config set --ai-provider gemini --ai-model gemini-3.1-pro-preview
```

模型建议（2026-03-07）：

- OpenAI：`gpt-5.4`、`gpt-5-mini`
- Gemini：`gemini-3.1-pro-preview`、`gemini-flash-latest`
- Qwen：`qwen3-max`、`qwen-plus-latest`

长文本上下文会自动压缩，阈值可用 `GEOCLAW_AI_MAX_CONTEXT_CHARS` 调整。

## 8. Memory（建议每周使用）

```bash
geoclaw-openai memory status
geoclaw-openai memory short --limit 10
geoclaw-openai memory long --limit 10
geoclaw-openai memory archive --before-days 7
geoclaw-openai memory search --query "武汉 选址" --scope all --top-k 5
```

## 9. TrackIntel 轨迹网络分析

```bash
python3 -m pip install --user --break-system-packages 'geoclaw-openai[network]'
bash scripts/run_trackintel_network_demo.sh
```

算法来源：Track-Intel（MIE Lab）。

## 10. 安全机制（重要）

- 输出必须落在 `data/outputs`。
- 禁止输出覆盖输入文件。

这可以降低实验过程中误删原始数据的风险。

## 11. 常见问题

1. `qgis_process not found`
- 在 `onboard` 里配置 `--qgis-process`，或设置 `GEOCLAW_OPENAI_QGIS_PROCESS`。

2. `update` 未检测到更新
- 默认跟踪 `origin/main`。若仓库使用 `master`，加 `--branch master`。

3. AI 调用失败
- 先用 `geoclaw-openai config show` 检查 provider/base_url/model/key 是否匹配。
