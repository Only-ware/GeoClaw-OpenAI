# GeoClaw 可直接用分析 Skill 快速上手（v3.1.3）

本文档面向新手，说明如何直接调用已注册的分析 Skill，并给出可复制命令。

## 1. 先决条件

```bash
geoclaw-openai --help
geoclaw-openai config show
geoclaw-openai skill -- --list
```

如果 `--list` 能看到 skill 列表，说明可直接开始。

## 2. 可直接用的分析 Skill（内置注册）

| Skill ID | 类型 | 典型用途 | 主要输出 |
|---|---|---|---|
| `location_analysis` | `pipeline` | 区位分析 | `grid_location.gpkg` |
| `site_selection` | `pipeline` | 选址分析 | `site_candidates.gpkg` |
| `mall_site_selection_qgis` | `pipeline` | 商场选址（可复现） | `mall_candidates.gpkg`（含经纬度） |
| `vector_basics_qgis` | `pipeline` | 矢量基础分析 | 矢量分析结果包 |
| `raster_basics_qgis` | `pipeline` | 栅格基础分析 | 栅格分析结果包 |
| `qgis_operator_skill` | `builtin` | 执行任意 QGIS 算子 | 由参数文件定义 |
| `network_trackintel_skill` | `builtin` | 轨迹网络分析 | `od_edges/nodes/trips` + summary |
| `mall_site_selection_llm` | `ai` | LLM 版商场选址策略解释 | 结构化文本结果 |

## 3. 最常用命令示例

### 3.1 区位分析

```bash
geoclaw-openai skill -- --skill location_analysis --set bbox="30.50,114.20,30.66,114.45"
```

### 3.2 选址分析（本地数据）

```bash
geoclaw-openai skill -- --skill site_selection --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/site_demo --skip-download
```

### 3.3 商场选址（QGIS 可复现）

```bash
geoclaw-openai skill -- --skill mall_site_selection_qgis --set city="武汉市" --set out_dir=data/outputs/mall_qgis_demo
```

### 3.4 矢量与栅格分析

```bash
geoclaw-openai skill -- --skill vector_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_vector
geoclaw-openai skill -- --skill raster_basics_qgis --set raw_dir=data/raw/wuhan_osm --set out_dir=data/outputs/demo_raster
```

### 3.5 通用 QGIS 算子（builtin）

```bash
geoclaw-openai skill -- --skill qgis_operator_skill --args "--algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml"
```

### 3.6 轨迹网络分析（builtin）

```bash
geoclaw-openai skill -- --skill network_trackintel_skill --args "--pfs-csv data/examples/trajectory/trackintel_demo_pfs.csv --out-dir data/outputs/network_trackintel_skill_demo"
```

### 3.7 LLM 选址策略说明（ai）

```bash
geoclaw-openai skill -- --skill mall_site_selection_llm --ai-input "请根据商圈密度、可达性、竞品距离给出前5候选点判据"
```

## 4. 参数使用规则

- `--set key=value`：给 `pipeline` 类型覆盖变量（可重复）。
- `--args "..."`：给 `builtin` 类型传原生命令参数字符串。
- `--arg token`：给 `builtin` 类型逐项传参数 token（可重复）。
- `--skip-download`：当输入数据已存在时，跳过下载步骤。

## 5. 输出结果在哪里

默认输出在 `data/outputs/`。建议每次实验显式设置 `out_dir`，例如：

```bash
--set out_dir=data/outputs/my_experiment_20260309
```

## 6. 常见问题

1. `skill not found`：先执行 `geoclaw-openai skill -- --list`，确认 ID 拼写。
2. `qgis_process not found`：执行 `geoclaw-openai onboard` 重新配置 QGIS 路径。
3. 输出被拦截：检查输出路径是否在 `data/outputs/` 内。
4. 想先安全评估再注册新 skill：

```bash
geoclaw-openai skill-registry assess --spec-file configs/examples/new_skill.json
```

## 7. 延伸阅读

- `docs/native-cases-and-skills.md`
- `docs/skill-authoring-spec.md`
- `docs/skill-case-mall-site-selection.md`

## 8. OpenClaw Skill 接入（兼容导入）

GeoClaw 支持把 OpenClaw 风格的 Skill 描述（JSON/YAML）转换为本地 Skill 并注册。

```bash
# 仅转换+评估（不写入注册表）
geoclaw-openai skill-registry import-openclaw \
  --spec-file configs/examples/openclaw_skill_example.yaml \
  --id-prefix oc_ \
  --dry-run

# 转换+注册（含确认）
geoclaw-openai skill-registry import-openclaw \
  --spec-file configs/examples/openclaw_skill_example.yaml \
  --id-prefix oc_ \
  --confirm
```

说明：
- 导入后仍会经过 GeoClaw 安全评估规则。
- OpenClaw `command` 会被映射为 GeoClaw `builtin`（仅允许 `run/operator/network/reasoning`）。
