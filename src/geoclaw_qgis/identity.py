from __future__ import annotations

from dataclasses import dataclass

from geoclaw_qgis.project_info import LAB_AFFILIATION, PROJECT_NAME, PROJECT_TAGLINE


@dataclass(frozen=True)
class GeoClawIdentity:
    name: str
    developer: str
    definition_en: str
    definition_zh: str
    core_features: tuple[str, ...]
    reference_files: tuple[str, ...]

    def prompt_block(self) -> str:
        features = "; ".join(self.core_features)
        refs = "; ".join(self.reference_files)
        return (
            f"Project name: {self.name}. "
            f"Developer: {self.developer}. "
            f"Definition: {self.definition_en} "
            "This project is NOT the Clawpack tsunami/flood simulation package named GeoClaw. "
            f"Core features: {features}. "
            f"Reference files: {refs}."
        )

    def answer_zh(self) -> str:
        features = "；".join(self.core_features)
        refs = "、".join(self.reference_files)
        return (
            f"{self.name} 是一个 GIS/GeoAI 空间分析智能体（不是 Clawpack 的海啸 GeoClaw）。\n"
            f"开发机构：{self.developer}。\n"
            f"主要功能：{features}。\n"
            f"参考文件：{refs}。"
        )

    def answer_en(self) -> str:
        features = "; ".join(self.core_features)
        refs = ", ".join(self.reference_files)
        return (
            f"{self.name} is a GIS/GeoAI spatial-analysis agent (not the Clawpack tsunami GeoClaw). "
            f"Developer: {self.developer}. "
            f"Core features: {features}. "
            f"References: {refs}."
        )


GEOCLAW_IDENTITY = GeoClawIdentity(
    name=PROJECT_NAME,
    developer=LAB_AFFILIATION,
    definition_en="A geospatial workflow agent built on QGIS processing for reproducible GIS + AI analysis.",
    definition_zh="一个基于 QGIS Processing 的可复现 GIS+AI 空间分析工作流智能体。",
    core_features=(
        "QGIS Processing spatial analysis and mapping",
        "Natural-language routing (chat -> executable workflows)",
        "Skill orchestration (pipeline/ai/builtin)",
        "Short-term and long-term memory",
        "SRE spatial reasoning and report generation",
        PROJECT_TAGLINE,
    ),
    reference_files=(
        "README.md",
        "docs/framework-design.md",
        "docs/technical-reference-geoclaw-openai.md",
        "docs/development-guide.md",
        "src/geoclaw_qgis/project_info.py",
        "src/geoclaw_qgis/cli/main.py",
    ),
)


def is_identity_question(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    keywords = (
        "what is geoclaw",
        "who developed",
        "who built",
        "what can geoclaw do",
        "geoclaw是什么",
        "谁开发",
        "谁做的",
        "主要功能",
        "参考文件",
        "what is geoclaw-openai",
    )
    return any(k in t for k in keywords)

