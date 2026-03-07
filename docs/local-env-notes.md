# 本地环境说明（当前机器）

检测时间：2026-03-07

## 结论

- `qgis_process` 可用，但不在系统 PATH。
- Homebrew Python (`/opt/homebrew/bin/python3`) 无法直接导入 `qgis` 模块。
- QGIS 自带 Python (`/Applications/QGIS.app/Contents/MacOS/bin/python3`) 可导入 PyQGIS，且 `processing` 可用。

## 推荐运行方式（当前阶段）

### 1) 直接走 qgis_process CLI（推荐）

```bash
/Applications/QGIS.app/Contents/MacOS/bin/qgis_process --version
/Applications/QGIS.app/Contents/MacOS/bin/qgis_process list
```

### 2) 走 PyQGIS（使用 QGIS 自带 Python）

```bash
/Applications/QGIS.app/Contents/MacOS/bin/python3 scripts/check_pyqgis.py
```

### 3) 可选：给 shell 增加快捷 PATH

```bash
export PATH="/Applications/QGIS.app/Contents/MacOS/bin:$PATH"
```

加入 `~/.zshrc` 后可直接调用 `qgis_process`。
