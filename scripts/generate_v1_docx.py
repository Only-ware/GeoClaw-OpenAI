#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "GeoClaw-OpenAI_v1.0_工程说明书.docx"

TITLE = "GeoClaw-OpenAI v1.0 工程说明书"
SUBTITLE = "UrbanComp Lab @ China University of Geosciences (Wuhan)"
TODAY = dt.date.today().isoformat()

sections: list[tuple[str, list[str]]] = [
    (
        "1. 工程目的",
        [
            "GeoClaw-OpenAI 面向科研与教学场景，提供可复现、可扩展的 GIS 分析工作流。",
            "项目目标是把数据获取、空间分析、专题制图、AI 辅助解释串联为统一流程，降低跨学科团队协作门槛。",
            "v1.0 版本强调稳定性、参数灵活性和初学者可用性，支持从入门到实验迭代的完整路径。",
        ],
    ),
    (
        "2. 开发者与组织",
        [
            "项目名称：GeoClaw-OpenAI",
            "版本：1.0.0",
            "开发者：UrbanComp Lab @ China University of Geosciences (Wuhan)",
            "维护方式：基于 QGIS Processing + Python 的模块化工程维护。",
        ],
    ),
    (
        "3. 项目结构",
        [
            "- configs/: 样式、技能注册表、参数示例文件。",
            "- pipelines/: 原生案例与教学案例（矢量/栅格）流程定义。",
            "- scripts/: 执行脚本（case、operator、demo、安装、日常回归）。",
            "- src/geoclaw_qgis/: CLI、provider、analysis API、配置管理、技能与 AI 客户端。",
            "- docs/: 技术参考、开发指南、学习手册、发布说明。",
            "- data/: 原始数据与输出结果。",
        ],
    ),
    (
        "4. 算法原理（核心）",
        [
            "4.1 数据获取原理：通过 Overpass API 抓取 OSM 数据，支持城市名地理编码（Nominatim）和 bbox 直接输入。",
            "4.2 矢量分析原理：以 native:buffer、clip、intersection、dissolve、fieldcalculator 等算子构建空间关系与指标计算。",
            "4.3 栅格分析原理：以热力核密度、重投影、掩膜裁剪、分区统计为主，构建栅格强度与格网统计指标。",
            "4.4 区位分析原理：多因子归一化 + 加权叠加，形成 LOCATION_SCORE 与等级分层。",
            "4.5 选址分析原理：先约束筛选（可行域）再综合评分排序，得到 SITE_RANK / SITE_CLASS。",
            "4.6 可复现机制：所有流程由 YAML 定义，输出 pipeline_report.json 记录参数、步骤、产物与版本归属。",
        ],
    ),
    (
        "5. 操作流程",
        [
            "5.1 环境准备：运行 check_local_env.sh，安装 geoclaw-openai，执行 onboard 完成初始化。",
            "5.2 基础运行：geoclaw-openai run --case native_cases --city \"武汉市\"。",
            "5.3 教学 demo：bash scripts/run_beginner_demos.sh（同时跑矢量与栅格示例）。",
            "5.4 参数迭代：run_qgis_pipeline.py 支持 --set、--set-json、--vars-file。",
            "5.5 单算法实验：geoclaw-openai operator 支持命令行参数、JSON 参数、YAML 参数文件。",
            "5.6 结果复核：在 QGIS 中加载输出 GPKG/TIF，检查字段、统计值、空间分布与专题图。",
        ],
    ),
    (
        "6. 给初学者的建议",
        [
            "建议 1：先跑通内置 demo，再改参数，不要一开始就改算法链路。",
            "建议 2：每次实验使用新 out_dir（按日期或实验编号），避免结果覆盖。",
            "建议 3：先理解字段含义再调整权重，避免出现‘结果可视化好看但解释不成立’。",
            "建议 4：把 vars 覆盖写入文件（--vars-file），比手工命令更易复现与分享。",
            "建议 5：出现错误先看 pipeline_report.json 和 step 失败位置，再看原始数据完整性。",
        ],
    ),
    (
        "7. 常见问题 Q&A",
        [
            "Q1: qgis_process 找不到怎么办？",
            "A1: 在 onboard 时指定 --qgis-process，或设置 GEOCLAW_OPENAI_QGIS_PROCESS。",
            "Q2: 城市名模式失败怎么办？",
            "A2: 检查网络与 geocode/overpass 可用性，必要时改用 --bbox 或 --data-dir。",
            "Q3: 本地目录需要哪些文件？",
            "A3: roads.geojson、water.geojson、hospitals.geojson、study_area.geojson。",
            "Q4: 为什么要输出 report？",
            "A4: 用于科研复现、团队审计和故障定位。",
            "Q5: operator 与 pipeline 区别是什么？",
            "A5: operator 适合单算子试验，pipeline 适合完整流程与批量复用。",
            "Q6: 参数太多怎么管理？",
            "A6: 使用 --vars-file 和 params-file，把实验参数文件化。",
            "Q7: 可以做别的城市吗？",
            "A7: 可以，建议先用 city/bbox 跑通，再针对本地数据特征调权重与阈值。",
            "Q8: AI 401 报错会影响 GIS 主流程吗？",
            "A8: 不影响，AI 是扩展层，核心空间分析可独立运行。",
            "Q9: 输出结果如何用于论文图表？",
            "A9: 使用 qgz + png 输出，并在文中记录 bbox、时间、参数与版本号。",
            "Q10: 后续怎么迭代到 1.x？",
            "A10: 建议先扩展路网最短路径可达性，再扩展自动分级与不确定性评估。",
        ],
    ),
    (
        "8. 版本说明",
        [
            f"文档生成日期：{TODAY}",
            "当前稳定版本：v1.0.0",
            "本说明书随工程发布，建议与 release-notes.md 配套阅读。",
        ],
    ),
]


def p(text: str, style: str | None = None) -> str:
    t = html.escape(text)
    p_pr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{p_pr}<w:r><w:t xml:space=\"preserve\">{t}</w:t></w:r></w:p>"


paras: list[str] = [
    p(TITLE, "Title"),
    p(SUBTITLE, "Subtitle"),
    p(f"发布日期：{TODAY}"),
    p(""),
]
for heading, lines in sections:
    paras.append(p(heading, "Heading1"))
    for line in lines:
        paras.append(p(line))


document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(paras)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
      <w:cols w:space="708"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>
'''

styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="40"/><w:szCs w:val="40"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr><w:b/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr>
  </w:style>
</w:styles>
'''

content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'''

rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'''

doc_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
'''

core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{html.escape(TITLE)}</dc:title>
  <dc:creator>UrbanComp Lab @ China University of Geosciences (Wuhan)</dc:creator>
  <cp:lastModifiedBy>GeoClaw-OpenAI</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{TODAY}T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{TODAY}T00:00:00Z</dcterms:modified>
  <dc:description>GeoClaw-OpenAI v1.0 工程说明书</dc:description>
</cp:coreProperties>
'''

app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>GeoClaw-OpenAI</Application>
</Properties>
'''

with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as zf:
    zf.writestr("[Content_Types].xml", content_types_xml)
    zf.writestr("_rels/.rels", rels_xml)
    zf.writestr("docProps/core.xml", core_xml)
    zf.writestr("docProps/app.xml", app_xml)
    zf.writestr("word/document.xml", document_xml)
    zf.writestr("word/styles.xml", styles_xml)
    zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)

print(str(OUTPUT))
