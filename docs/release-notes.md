# GeoClaw-OpenAI Release Notes

## v1.0.0 (2026-03-07)

稳定发布说明：

1. 形成完整 GIS 分析产品闭环  
   - 支持城市名 / bbox / 本地目录三种输入方式。  
   - 支持区位分析、选址分析、综合案例与专题出图。

2. 空间分析能力全面增强  
   - 新增栅格与矢量操作 API（`VectorAnalysisService`、`RasterAnalysisService`）。  
   - 新增单算法灵活运行入口 `geoclaw-openai operator`。

3. 参数定义灵活化  
   - pipeline 支持 `--set`、`--set-json`、`--vars-file`。  
   - operator 支持 `--param`、`--param-json`、`--params-file`。

4. 面向科研与教学的文档体系完善  
   - 新增科研学习手册、版本发布说明、示例 pipeline 与 demo 脚本。  
   - 新增工程级 `.docx` 说明文档（含目的、结构、原理、流程、Q&A）。

5. 机构声明与可追踪性  
   - 代码和运行输出统一声明：  
     `UrbanComp Lab @ China University of Geosciences (Wuhan)`。  
   - 输出结果包含版本与归属字段，便于科研复现与团队协作。

## v0.2.0 (2026-03-07)

主要迭代：

1. 栅格/矢量分析能力增强  
   - 新增 `VectorAnalysisService` 与 `RasterAnalysisService` Python API。
   - 新增教学 pipeline：`vector_basics.yaml`、`raster_basics.yaml`。

2. 参数定义灵活性增强  
   - `run_qgis_pipeline.py` 新增 `--set-json`、`--vars-file`。
   - 新增 `geoclaw-openai operator` 单算法入口，支持 `--param`、`--param-json`、`--params-file`。

3. 多输入源与初学者 demo 完整链路  
   - `geoclaw-openai run` 支持 `--city` / `--bbox` / `--data-dir`。
   - 新增 `scripts/run_beginner_demos.sh` 一键示例。

4. 项目归属声明与可追踪性  
   - 代码内新增机构声明：
     `UrbanComp Lab @ China University of Geosciences (Wuhan)`。
   - pipeline/operator 输出加入版本与归属信息。
