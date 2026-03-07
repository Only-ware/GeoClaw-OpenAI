# GeoClaw-OpenAI 框架设计（V0）

## 1. 目标

构建一个“类似 OpenClaw 的 GeoClaw 工具”，但以 **QGIS processing 生态** 为核心执行引擎：

- 执行层优先使用 `qgis_process`
- 可选使用 PyQGIS 作为增强后端
- 面向流程编排、可重复执行、可观察日志

## 2. 架构分层

### 2.1 核心层（`core/`）

- `Pipeline`: 管理步骤顺序、输入输出、失败回滚策略（后续）
- `StepSpec`: 统一步骤声明（算法名、参数、输入依赖、输出定义）
- `ExecutionContext`: 运行上下文（工作目录、临时目录、日志）

### 2.2 执行提供层（`providers/`）

- `QgisProcessRunner`: 调用 `qgis_process run ...`
- `PyQgisRunner`（后续）: 使用 PyQGIS API 直接执行 processing 算法

职责：

- 参数序列化与命令构建
- 标准输出/错误捕获
- 错误码和异常统一

### 2.3 算子层（`analysis/`）

封装基础空间分析能力（算法模板 + 参数校验）：

- `buffer`
- `clip`
- `intersection`
- `dissolve`
- `reproject`

### 2.4 制图层（`cartography/`）

- 样式模板应用（QML/SLD）
- 布局导出（PDF/PNG）
- 批量出图入口

### 2.5 I/O 层（`io/`）

- 数据源描述（GeoPackage / Shapefile / GeoJSON / Raster）
- 输出管理（命名规范、版本化目录）

### 2.6 CLI 层（`cli/`）

- `geoclaw-openai env check`
- `geoclaw-openai run pipeline.yaml`
- `geoclaw-openai analysis buffer ...`

## 3. 运行模型

1. 解析任务配置（YAML/JSON）
2. Pipeline 拓扑排序并校验输入依赖
3. 调用 Provider 执行算法
4. 记录结果、产物路径、日志

## 4. 最小可交付（MVP）

- 环境检测命令（完成）
- 3 个矢量分析算子（buffer/clip/dissolve）
- 1 个制图导出流程（单布局导出 PNG）
- 1 个 pipeline YAML 示例 + smoke test

## 5. 测试策略

- `env smoke`: 检查 `qgis_process` / PyQGIS / GDAL
- `operator smoke`: 小样本数据跑通
- `golden output`: 对关键输出进行几何计数、范围、CRS 校验

## 6. 扩展策略

- 插件式算子注册（按算法名自动发现）
- Provider 回退机制（优先 CLI，必要时 PyQGIS）
- 增量缓存（输入未变时跳过步骤）
