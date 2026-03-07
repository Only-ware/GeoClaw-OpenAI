# GeoClaw CLI 安装与 Onboard（v1.0.0）

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

# 按城市名运行内置案例
geoclaw-openai run --case native_cases --city "武汉市"

# 按 bbox 运行
geoclaw-openai run --case location_analysis --bbox "30.50,114.20,30.66,114.45"

# 按本地数据目录运行
geoclaw-openai run --case site_selection --data-dir data/raw/wuhan_osm --skip-download

# 单算法灵活运行
geoclaw-openai operator --algorithm native:buffer --params-file configs/examples/operator_buffer_params.yaml
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
