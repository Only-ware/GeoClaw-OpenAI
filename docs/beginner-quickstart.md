# GeoClaw-OpenAI 新手快速上手（持续维护）

本文档面向不写 Python 的新手用户，目标是用最少命令完成安装、配置、运行和查看结果。

安装总入口（含 Windows + QGIS）：
- README 安装章节：`README.md` 的「3. 安装与初始化（新手完整流程）」
- 详细 Onboard 文档：`docs/cli-onboard.md`

## 1. 你将得到什么

完成本文后，你可以直接用自然语言执行问题，例如：

`武汉最适合建商场的前5个地点`

并得到：

- 候选点空间结果（GeoPackage）
- 推理报告（Markdown）

## 2. 环境准备

需要具备：

- macOS / Linux / Windows
- `python3`（建议 3.10+）
- QGIS（需包含 `qgis_process`）

在项目根目录执行：

```bash
bash scripts/check_local_env.sh
```

## 3. 安装与首次配置

```bash
bash scripts/install_geoclaw_openai.sh
geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh
```

`onboard` 会引导你配置：

- AI provider（OpenAI / Qwen / Gemini / Ollama）
- API Key（v3.1.2 起输入为可见模式，重配时提示脱敏 key 片段）
- 默认模型
- 默认 bbox

如使用本地模型，推荐选 `ollama`，默认端点为 `http://127.0.0.1:11434/v1`。

### 3.1 Windows 用户（PowerShell + QGIS）

如果你是 Windows 新手，建议直接按 README 的 Windows 流程操作：

1. 安装 QGIS（下载页：<https://qgis.org/download/>）
2. 在 PowerShell 里确认 `qgis_process.exe` 路径
3. 执行 `git clone` + `py -3 -m pip install --user -e .`
4. 执行 `geoclaw-openai onboard --qgis-process "<你的qgis_process路径>"`

可直接参考：`README.md` 的「3.6 Windows（PowerShell）安装流程 + QGIS 安装」。

## 4. 第一条命令（端到端）

```bash
geoclaw-openai nl "武汉最适合建商场的前5个地点，输出结果和简要解释" \
  --use-sre \
  --sre-reasoner-mode deterministic \
  --sre-report-out data/outputs/reasoning/wuhan_mall_top5_report.md \
  --execute
```

执行完成后，重点看两个文件：

- `data/outputs/mall_site_qgis/mall_candidates.gpkg`
- `data/outputs/reasoning/wuhan_mall_top5_report.md`

## 5. 不执行先预览（推荐）

先看系统将执行什么命令：

```bash
geoclaw-openai nl "武汉最适合建商场的前5个地点"
```

这会输出 `command_preview` 和 `cli_args`，确认后再加 `--execute`。

## 5.1 聊天模式端到端（不会写代码也可用）

```bash
geoclaw-openai chat \
  --message "请你下载景德镇的数据，并分析最适合建设商场的前5个地址，输出报告" \
  --no-ai \
  --execute \
  --use-sre \
  --sre-report-out data/outputs/reasoning/chat_jingdezhen_mall_top5_report.md
```

参考案例产物目录：
- `data/examples/chat_mode/jingdezhen_mall_top5/README.md`

## 6. 常见问题

1. 报错找不到 `qgis_process`
   - 重新安装 QGIS，或在 onboard/config 中指定路径。
2. API 报错
   - 检查 `~/.geoclaw-openai/env.sh` 的 key 与 base_url。
3. 结果数量不对
   - 在问题里明确写 `前N个`，例如 `前5个`。
4. 输出文件未生成
   - 检查输出是否在 `data/outputs/` 下（系统安全策略会限制输出目录）。

如果你暂时不知道如何继续，可用闲聊模式获取下一步建议：

```bash
geoclaw-openai chat --message "我这里失败了，下一步怎么排查？" --no-ai
```

## 7. 教程维护约定

该文档为长期维护文档。以下变更必须同步更新本教程：

- CLI 参数变化（新增/删除/重命名）
- 默认模型或 provider 变更
- 样例输出路径变化
- 新手入口命令变化

建议每次发布前额外执行：

```bash
bash scripts/e2e_complex_nl_suite.sh
```

用于验证自然语言端到端能力在复杂场景下仍可用。
