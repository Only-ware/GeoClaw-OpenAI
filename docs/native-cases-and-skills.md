# GeoClaw 原生案例与 Skill 扩展（v2.3.0）

机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 1. 原生案例

GeoClaw 原生支持两个核心 GIS 案例：

- 区位分析：`location_analysis`
- 选址分析：`site_selection`

统一入口：

```bash
# 区位 + 选址
geoclaw-openai run --case native_cases --city "武汉市"

# 仅区位
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 仅选址（本地数据）
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download
```

输入参数 `--city`、`--bbox`、`--data-dir` 互斥。

## 2. 案例输出

- 区位输出：`data/outputs/<tag>_location/grid_location.gpkg`
- 选址输出：`data/outputs/<tag>_site/site_candidates.gpkg`

关键字段：

- 区位：`LOCATION_SCORE`、`LOCATION_LEVEL`、`ACCESS_NORM`、`UNDERSERVED_NORM`
- 选址：`SITE_RANK`、`SITE_SCORE`、`SITE_CLASS`

## 3. Skill 扩展机制

注册表：`configs/skills_registry.json`

内置类型：

- `pipeline`：执行空间流程
- `ai`：调用外部 AI API

常用命令：

```bash
geoclaw-openai skill -- --list
geoclaw-openai skill -- --skill location_analysis
geoclaw-openai skill -- --skill site_selection --with-ai --ai-input "输出建设优先级"
```

## 4. AI Provider 支持

支持：`openai`、`qwen`、`gemini`

```bash
# 初始化时指定 provider
geoclaw-openai onboard --non-interactive --ai-provider qwen --api-key "<QWEN_KEY>"

# 后续切换
geoclaw-openai config set --ai-provider gemini --ai-model gemini-2.0-flash
```

## 5. 自动上下文压缩

Skill 的 AI 输入文本过长时会自动压缩，默认开启。可通过 `GEOCLAW_AI_MAX_CONTEXT_CHARS` 调整阈值。

## 6. Memory 与知识沉淀

每次任务自动写短期 memory，结束后自动复盘到长期 memory；可归档与检索：

```bash
geoclaw-openai memory archive --before-days 7
geoclaw-openai memory search --query "选址评分" --scope all --top-k 5
```

## 7. TrackIntel 复杂网络模块

GeoClaw 支持轨迹数据复杂网络分析（算法来源：Track-Intel, MIE Lab）。

```bash
bash scripts/run_trackintel_network_demo.sh
```

输出目录示例：`data/outputs/network_trackintel_demo/`

## 8. 安全约束

- 所有输出必须在 `data/outputs`。
- 禁止将输出写回输入文件。

## 9. TODO（Skill 方向）

- TODO: 支持 skill 级权限边界（文件、命令、网络）。
- TODO: 支持 skill 依赖图可视化，便于复杂编排调试。
