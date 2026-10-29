from typing import ClassVar, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class ContentValidationInput(BaseModel):
    """Input schema for the content validator tool."""
    content: str = Field(..., description="The blog post content to validate")
    keyword: str = Field(..., description="The primary keyword for the content")


class ContentValidatorTool(BaseTool):
    name: str = "content_validator"
    description: str = (
        "Validates that a blog post follows the 9-step article formula for the Speedbots content "
        "strategy. Checks for direct answer, business problem, real workflows, implementation steps, "
        "cost factors, risks and controls, case example, FAQ, and specific CTA. Returns a checklist "
        "score and recommendations."
    )
    args_schema: Type[BaseModel] = ContentValidationInput

    REQUIREMENTS: ClassVar[dict] = {
        "Direct Answer": {
            "keywords": ["automation", "artificial intelligence", "ai"],
            "min_words": 80,
            "section_hint": "first 150 words",
        },
        "Business Problem": {
            "keywords": ["problem", "manual", "pain", "time", "hours", "error"],
            "min_words": 200,
        },
        "Real Workflows": {
            "keywords": ["before automation", "after automation", "workflow", "step"],
            "min_words": 300,
        },
        "Implementation Steps": {
            "keywords": ["step", "implement", "audit", "integrate", "deploy"],
            "min_words": 200,
        },
        "Cost Factors": {
            "keywords": ["cost", "price", "rm", "sgd", "aud", "inr", "payback", "save", "rm "],
            "min_words": 100,
        },
        "Risks and Controls": {
            "keywords": ["risk", "mitigat", "control", "security", "accuracy", "compliance"],
            "min_words": 100,
        },
        "Case Example": {
            "keywords": ["results", "company", "firm", "reduced", "improved", "solution"],
            "min_words": 100,
        },
        "FAQ": {
            "keywords": ["q:", "faq", "?"],
            "min_count": 5,
        },
        "Specific CTA": {
            "keywords": ["book", "assessment", "workflow", "estimate", "demo", "schedule"],
            "section_hint": "final section",
        },
    }

    def _run(self, content: str, keyword: str) -> str:
        content_lower = content.lower()
        report = []
        report.append("=== CONTENT STRATEGY VALIDATION REPORT ===")
        report.append(f"Keyword: {keyword}")
        word_count = len(content.split())
        report.append(f"Total Words: {word_count}")

        passes = 0
        total = len(self.REQUIREMENTS)

        for section, rules in self.REQUIREMENTS.items():
            matched_keywords = [k for k in rules["keywords"] if k in content_lower]
            match_ratio = len(matched_keywords) / len(rules["keywords"])
            status = "PASS" if match_ratio >= 0.5 else "WARN"
            if status == "PASS":
                passes += 1
            report.append(f"[{status}] {section}: matched {len(matched_keywords)}/{len(rules['keywords'])} keyword signals")

        score = (passes / total * 100) if total > 0 else 0
        report.append("")
        report.append(f"Strategy Compliance Score: {score:.0f}%")
        report.append(f"Summary: {passes}/{total} sections validated")

        if score >= 80:
            report.append("Recommendation: APPROVED")
        elif score >= 60:
            report.append("Recommendation: APPROVED WITH REVISION")
        else:
            report.append("Recommendation: REJECTED - major gaps in article formula")

        return "\n".join(report)
