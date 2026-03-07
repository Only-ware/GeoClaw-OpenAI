# GeoClaw CLI 安装与 Onboard（v1.1.0）

## 1) 安装

```bash
bash scripts/install_geoclaw_openai.sh
```

安装完成后会得到 `geoclaw-openai` 命令。  
机构声明：UrbanComp Lab @ China University of Geosciences (Wuhan)

## 2) 交互式初始化

```bash
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

`env.sh` 会自动把 Python user bin（例如 `/Users/<you>/Library/Python/<ver>/bin`）加入 `PATH`，避免新终端出现 `geoclaw-openai: command not found`。

`onboard` 会写入：

- `~/.geoclaw-openai/config.json`
- `~/.geoclaw-openai/.env`
- `~/.geoclaw-openai/env.sh`

## 3) 非交互初始化（CI/自动化）

```bash
geoclaw-openai onboard --non-interactive \
  --api-key "<OPENAI_KEY>" \
  --ai-base-url "https://api.openai.com/v1" \
  --ai-model "gpt-4.1-mini" \
  --qgis-process "/Applications/QGIS.app/Contents/MacOS/bin/qgis_process" \
  --default-bbox "30.50,114.20,30.66,114.45" \
  --registry "configs/skills_registry.json"
```

## 4) 常用命令

```bash
geoclaw-openai config show
geoclaw-openai env
geoclaw-openai skill -- --list
geoclaw-openai memory status
geoclaw-openai update --check-only
geoclaw-openai nl "用武汉市做选址分析，前20个，出图"

# 按城市名运行内置案例
geoclaw-openai run --case native_cases --city "武汉市"

# 按 bbox 运行
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 按本地数据目录运行
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# 单算法灵活运行
geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml

# 自然语言执行（先预览，后执行）
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析"
geoclaw-openai nl "按bbox 30.50,114.20,30.66,114.45 跑区位分析" --execute
```

`geoclaw-openai run --help` 可查看全部参数（`--tag`、`--out-root`、`--with-maps` 等）。
其中 `--city`、`--bbox`、`--data-dir` 为互斥参数。

## 5) 关键环境变量

- `GEOCLAW_OPENAI_BASE_URL`
- `GEOCLAW_OPENAI_API_KEY`
- `GEOCLAW_OPENAI_MODEL`
- `GEOCLAW_OPENAI_QGIS_PROCESS`
- `GEOCLAW_OPENAI_DEFAULT_BBOX`
- `GEOCLAW_OPENAI_SKILL_REGISTRY`

## 6) Memory 与 Update

- 每次 `geoclaw-openai` 任务（除 `memory` 命令本身）会自动写入短期 memory，并自动复盘写入长期 memory。
- 短期 memory 目录：`~/.geoclaw-openai/memory/short/`
- 长期 memory 文件：`~/.geoclaw-openai/memory/long_term.jsonl`

常用命令：

```bash
geoclaw-openai memory status
geoclaw-openai memory short --limit 10
geoclaw-openai memory long --limit 10

# 手工复盘某个短期任务并写入长期 memory
geoclaw-openai memory review --task-id "<TASK_ID>" --summary "复盘总结"

# 检查更新
geoclaw-openai update --check-only

# 拉取并更新（默认跟踪 origin/main）
geoclaw-openai update
```
