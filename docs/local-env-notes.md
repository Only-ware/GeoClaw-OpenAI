# 本地环境说明（v3.1.1）

检测时间：2026-03-09

## 1. 当前结论

- `qgis_process` 可用，但不一定在系统 PATH。
- 系统 Python 可能无法导入 `qgis`，这是常见现象。
- QGIS 自带 Python 可用于 PyQGIS 脚本。

## 2. 建议的检查命令

```bash
# 1) 基础环境
bash scripts/check_local_env.sh

# 2) qgis_process 检查
/Applications/QGIS.app/Contents/MacOS/bin/qgis_process --version

# 3) CLI 可用性
geoclaw-openai --help

# 4) Profile layers 可用性
geoclaw-openai profile show
```

## 3. provider 与配置检查

```bash
geoclaw-openai config show
```

重点确认：

- `ai_provider` 是否正确（openai/qwen/gemini/ollama）
- `ai_base_url` 与 provider 是否匹配
- `ai_model` 是否存在
- `qgis_process` 路径是否可执行
- `soul.md` / `user.md` 路径是否可读

新手安装入口：
- `docs/beginner-quickstart.md`
- `README.md` 的「3. 安装与初始化（新手完整流程）」

## 4. 常见排障

1. `geoclaw-openai: command not found`
- 先执行：`source ~/.geoclaw-openai/env.sh`

2. `qgis_process not found`
- 在 `onboard` 中设置 `--qgis-process`，或更新 config。

3. 输出路径报安全错误
- 输出路径应放在 `data/outputs`，不可写回 `data/raw`。
