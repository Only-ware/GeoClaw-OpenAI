# GeoClaw-OpenAI 团队一页安装手册

适用场景：团队快速统一安装、升级、重装与排障。

仓库地址：<https://github.com/whuyao/GeoClaw-OpenAI>

## 1) 新装（macOS/Linux）

```bash
git clone https://github.com/whuyao/GeoClaw-OpenAI.git
cd GeoClaw-OpenAI

bash scripts/check_local_env.sh
bash scripts/install_geoclaw_openai.sh

geoclaw-openai onboard
source ~/.geoclaw-openai/env.sh

geoclaw-openai --version
geoclaw-openai web --open-browser
```

## 2) 已安装用户升级到最新

```bash
cd GeoClaw-OpenAI
git pull origin master
bash scripts/reinstall_geoclaw_openai.sh
geoclaw-openai --version
```

## 3) Windows（PowerShell）

```powershell
git clone https://github.com/whuyao/GeoClaw-OpenAI.git
cd GeoClaw-OpenAI

py -3 -m pip install --user -e .
geoclaw-openai onboard --qgis-process "C:\Program Files\QGIS 3.40.0\bin\qgis_process.exe"

geoclaw-openai --version
geoclaw-openai web --host 127.0.0.1 --port 8765
```

## 4) 常用启动

```bash
# 命令行连续对话
geoclaw-openai chat --interactive --session-id team_demo --new-session

# Web 试用版
geoclaw-openai web --open-browser
```

## 5) 卸载 / 重装

```bash
# 预览
geoclaw-openai uninstall --dry-run --yes
geoclaw-openai reinstall --dry-run --yes

# 执行
geoclaw-openai uninstall --yes
geoclaw-openai reinstall --yes

# 连同本地配置和记忆一起清理
geoclaw-openai uninstall --purge-home --yes
```

## 6) 故障排查（最短）

```bash
geoclaw-openai config show
geoclaw-openai env
geoclaw-openai chat --message "测试连通性" --with-ai
```

- `qgis_process not found`：重新执行 `onboard --qgis-process <path>`。
- `command not found: geoclaw-openai`：把用户 bin 目录加入 `PATH`（常见为 `~/Library/Python/*/bin` 或 `~/.local/bin`）。
