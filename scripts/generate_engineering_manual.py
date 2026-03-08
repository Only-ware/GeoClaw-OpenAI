#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

ROOT = Path(__file__).resolve().parents[1]
DOCX_OUTPUT = ROOT / "GeoClaw-OpenAI_工程说明书.docx"
PDF_OUTPUT = ROOT / "GeoClaw-OpenAI_工程说明书.pdf"

TITLE = "GeoClaw-OpenAI 工程说明书"
SUBTITLE = "UrbanComp Lab @ China University of Geosciences (Wuhan)"
VERSION = "3.1.0"
TODAY = dt.date.today().isoformat()

sections: list[tuple[str, list[str]]] = [
    (
        "1. 工程目的",
        [
            "GeoClaw-OpenAI 面向科研、教学与工程团队，提供可复现的 GIS+AI 全流程能力。",
            "项目目标是将数据获取、空间分析、制图表达、AI 解释、Skill 扩展与任务记忆闭环统一到单一 CLI。",
            "v3.1.0 在 SRE+NL+Skill+Memory 稳定闭环基础上，新增本地大模型与 profile 对话演化机制。",
        ],
    ),
    (
        "2. 开发者与组织",
        [
            "项目名称：GeoClaw-OpenAI",
            f"版本：{VERSION}",
            "开发机构：UrbanComp Lab @ China University of Geosciences (Wuhan)",
            "技术基线：QGIS Processing + Python CLI + 可插拔 AI Provider。",
        ],
    ),
    (
        "3. 项目结构",
        [
            "- configs/: 配置、skill 注册表、示例输入与风险样例。",
            "- data/: 原始数据、轨迹样例、输出结果与演示产物。",
            "- docs/: 技术参考、学习手册、release notes、skill 规范文档。",
            "- pipelines/: 原生分析流程与教学案例流程。",
            "- scripts/: 安装、回归、demo、工程文档生成脚本。",
            "- src/geoclaw_qgis/: CLI、analysis、providers、skills、memory、profile、security。",
            "- soul.md / user.md: 系统层与用户层长期配置文档。",
        ],
    ),
    (
        "4. 核心算法与实现原理",
        [
            "4.1 数据输入：支持城市名、bbox、本地目录三种模式，统一进入可复现的流水线执行。",
            "4.2 区位分析：多指标标准化后加权融合，输出 LOCATION_SCORE 与等级分类。",
            "4.3 选址分析：约束筛选 + 综合评分排序，输出 SITE_RANK 与 SITE_CLASS。",
            "4.4 栅格/矢量分析：基于 QGIS Processing 算子与 pipeline 参数化运行。",
            "4.5 自然语言入口：NL 解析为 CLI 执行计划，可预览或直接执行。",
            "4.5.1 端到端报告：NL 在启用 SRE 时可直接输出标准化推理报告（受输出目录安全策略约束）。",
            "4.6 Soul/User 分层：soul.md 定义系统边界，user.md 定义用户长期偏好，统一解析后供 planner/router/report/memory 复用。",
            "4.7 Skill 扩展：支持 LLM 技能与 QGIS 技能双路径，并提供注册前安全评估。",
            "4.8 Memory 体系：短期记录、长期复盘、归档与向量检索，支持任务经验复用。",
            "4.9 轨迹网络：融合 Track-Intel 思路，输出 OD 边、节点、行程与网络摘要。",
        ],
    ),
    (
        "5. 3.1.0 版本新增重点",
        [
            "5.1 新增 Ollama 本地大模型 provider，并接入 onboard/config set 全链路。",
            "5.2 新增 profile evolve：支持根据对话摘要更新 user.md/soul.md 覆盖层。",
            "5.3 soul 安全边界字段锁定：重要安全与执行约束不可通过对话改写。",
            "5.4 新增 NL->profile 路由能力：自然语言可触发 profile 演化命令。",
            "5.5 day-run 与单元测试矩阵扩展，覆盖 profile evolve 与 provider 兼容性。",
            "5.6 data 目录持续跟踪，支持新用户直接复现实验样例。",
            "5.7 版本与文档体系升级到 v3.1.0。",
        ],
    ),
    (
        "6. 操作流程（建议）",
        [
            "6.1 环境检查：bash scripts/check_local_env.sh。",
            "6.2 安装与初始化：bash scripts/install_geoclaw_openai.sh && geoclaw-openai onboard。",
            "6.3 初始化 profile：geoclaw-openai profile init && geoclaw-openai profile show。",
            "6.4 对话演化 profile：geoclaw-openai profile evolve --target user --summary \"...\" --set preferred_language=Chinese。",
            "6.5 标准分析：geoclaw-openai run --case native_cases --city \"武汉市\"。",
            "6.6 端到端询问+报告：geoclaw-openai nl \"商场选址分析\" --use-sre --sre-report-out data/outputs/reasoning/nl_report.md。",
            "6.7 Skill 安全评估：geoclaw-openai skill-registry assess --spec-file <skill.json>。",
            "6.8 通过评估后注册：geoclaw-openai skill-registry register --spec-file <skill.json> --confirm。",
            "6.9 回归测试：python3 -m unittest discover -s src/geoclaw_qgis/tests。",
            "6.10 复杂端到端测试：bash scripts/e2e_complex_nl_suite.sh。",
        ],
    ),
    (
        "7. 初学者建议",
        [
            "建议 1：先运行内置 demo，再改参数，再扩展新 Skill。",
            "建议 2：每次实验使用独立输出目录，保证结果可追溯。",
            "建议 3：在提交 Skill 前先运行 assess，避免高风险行为注入。",
            "建议 4：将实验参数落盘到 YAML/JSON，提高复现实验成功率。",
            "建议 5：保留 memory 复盘记录，积累团队的知识资产。",
        ],
    ),
    (
        "8. 常见问题 Q&A",
        [
            "Q1: qgis_process 找不到怎么办？ A1: 在 onboard 指定路径或设置 GEOCLAW_OPENAI_QGIS_PROCESS。",
            "Q2: AI Key 配置后仍失败？ A2: 先 geoclaw-openai config show 检查 provider/base_url/model。",
            "Q3: 为什么 Skill 注册失败？ A3: 先看 assess 风险等级，high 风险需先修复行为。",
            "Q4: 为什么输出被拦截？ A4: 输出目录必须位于 data/outputs 且不能覆盖输入路径。",
            "Q5: 如何做跨城市复用？ A5: 优先使用 city/bbox 模式并把参数抽离为 vars 文件。",
        ],
    ),
    (
        "9. 文档与维护说明",
        [
            f"文档生成日期：{TODAY}",
            f"当前版本：v{VERSION}",
            "测试状态：单元测试、day-run、复杂 NL 端到端回归通过。",
            "维护建议：发布前同步检查 README、CHANGELOG、release-notes、工程说明书。",
        ],
    ),
]


def paragraph_xml(text: str, style: str | None = None) -> str:
    escaped = html.escape(text)
    p_pr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{p_pr}<w:r><w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'


def build_docx(output: Path) -> None:
    paragraphs: list[str] = [
        paragraph_xml(TITLE, "Title"),
        paragraph_xml(SUBTITLE, "Subtitle"),
        paragraph_xml(f"版本：v{VERSION}"),
        paragraph_xml(f"发布日期：{TODAY}"),
        paragraph_xml(""),
    ]

    for heading, lines in sections:
        paragraphs.append(paragraph_xml(heading, "Heading1"))
        for line in lines:
            paragraphs.append(paragraph_xml(line))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:w10="urn:schemas-microsoft-com:office:word" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">
  <w:body>
    {''.join(paragraphs)}
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
  <dc:description>GeoClaw-OpenAI 工程说明书（v{VERSION}）</dc:description>
</cp:coreProperties>
'''

    app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>GeoClaw-OpenAI</Application>
</Properties>
'''

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr("[Content_Types].xml", content_types_xml)
        zip_file.writestr("_rels/.rels", rels_xml)
        zip_file.writestr("docProps/core.xml", core_xml)
        zip_file.writestr("docProps/app.xml", app_xml)
        zip_file.writestr("word/document.xml", document_xml)
        zip_file.writestr("word/styles.xml", styles_xml)
        zip_file.writestr("word/_rels/document.xml.rels", doc_rels_xml)


def extract_docx_lines(docx_path: Path) -> list[str]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(docx_path, "r") as zip_file:
        document_xml = zip_file.read("word/document.xml")
    root = ET.fromstring(document_xml)

    lines: list[str] = []
    for paragraph in root.findall(".//w:body/w:p", namespace):
        texts = [node.text for node in paragraph.findall(".//w:t", namespace) if node.text]
        merged = "".join(texts).strip()
        if merged:
            lines.append(merged)
    return lines


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    except Exception:
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ZH_Title",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=26,
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "ZH_Subtitle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        spaceAfter=8,
    )
    heading_style = ParagraphStyle(
        "ZH_Heading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=14,
        leading=20,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ZH_Body",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=16,
    )

    lines = extract_docx_lines(docx_path)
    story = []
    for idx, line in enumerate(lines):
        safe_line = html.escape(line)
        if idx == 0:
            story.append(Paragraph(safe_line, title_style))
        elif idx in (1, 2, 3):
            story.append(Paragraph(safe_line, subtitle_style))
        elif line[0].isdigit() and ". " in line[:8]:
            story.append(Paragraph(safe_line, heading_style))
        else:
            story.append(Paragraph(safe_line, body_style))
        story.append(Spacer(1, 4))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50,
        title=TITLE,
        author="UrbanComp Lab @ China University of Geosciences (Wuhan)",
    )
    doc.build(story)


def main() -> None:
    build_docx(DOCX_OUTPUT)
    convert_docx_to_pdf(DOCX_OUTPUT, PDF_OUTPUT)
    print(str(DOCX_OUTPUT))
    print(str(PDF_OUTPUT))


if __name__ == "__main__":
    main()
