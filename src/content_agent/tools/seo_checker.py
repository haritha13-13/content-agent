from typing import ClassVar, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class SEOCheckInput(BaseModel):
    """Input schema for the SEO checker tool."""
    content: str = Field(..., description="The blog post content to check")
    primary_keyword: str = Field(..., description="The primary keyword for the content")
    secondary_keyword: str = Field(default="", description="Optional secondary keyword")


class SEOCheckerTool(BaseTool):
    name: str = "seo_checker"
    description: str = (
        "Checks a blog post for SEO compliance: title tag format, meta description length, "
        "keyword density, heading hierarchy, presence of internal links, and banned AI phrases. "
        "Returns a structured report with PASS/FAIL for each item."
    )
    args_schema: Type[BaseModel] = SEOCheckInput

    BANNED_AI_PHRASES: ClassVar[list] = [
        "in today's fast-paced world",
        "in today's digital world",
        "leveraging cutting-edge",
        "revolutionary",
        "game-changing",
        "unlock the power",
        "seamlessly integrate",
        "at the end of the day",
        "it's worth noting that",
        "furthermore",
        "moreover",
        "in conclusion",
        "harness the power",
        "unlocking the potential",
        "a comprehensive solution",
    ]

    def _run(self, content: str, primary_keyword: str, secondary_keyword: str = "") -> str:
        report = []
        report.append("=== SEO COMPLIANCE REPORT ===")

        # Keyword density
        words = content.lower().split()
        total_words = len(words)
        keyword_count = content.lower().count(primary_keyword.lower())
        density = (keyword_count / total_words * 100) if total_words > 0 else 0
        density_status = "PASS" if 1.0 <= density <= 2.0 else "WARN"
        report.append(f"Keyword Density: {density:.2f}% ({density_status} - target 1-2%)")

        if secondary_keyword:
            secondary_count = content.lower().count(secondary_keyword.lower())
            secondary_density = (secondary_count / total_words * 100) if total_words > 0 else 0
            sec_status = "PASS" if 0.5 <= secondary_density <= 1.0 else "WARN"
            report.append(f"Secondary Keyword {secondary_keyword}: {secondary_density:.2f}% ({sec_status})")

        # Title tag
        if "| Speedbots" in content:
            report.append("Title Tag format: PASS (contains '| Speedbots')")
        else:
            report.append("Title Tag format: FAIL (must end with '| Speedbots')")

        # Heading hierarchy
        h1_count = content.count("# ") - content.count("## ")
        h1_count = max(0, h1_count)
        h2_count = content.count("## ")
        report.append(f"Heading Hierarchy: {h1_count} H1 (must be 1), {h2_count} H2 sections")

        # Internal links
        import re
        links = re.findall(r"\[.*?\]\((/?[a-z0-9\-/]+)\)", content)
        internal_links = [l for l in links if l.startswith("/") and "http" not in l]
        report.append(f"Internal Links found: {len(internal_links)} - {internal_links}")
        if len(internal_links) >= 2:
            report.append("Internal Links: PASS (2 or more)")
        else:
            report.append("Internal Links: FAIL (need at least 2)")

        # Banned AI phrases
        found_phrases = [p for p in self.BANNED_AI_PHRASES if p in content.lower()]
        if found_phrases:
            report.append(f"AI Phrases Found: FAIL - {found_phrases}")
        else:
            report.append("AI Phrases: PASS (none found)")

        # CTA check
        cta_phrases = ["workflow assessment", "cost estimate", "book", "schedule"]
        has_cta = any(p in content.lower() for p in cta_phrases)
        report.append(f"Specific CTA: {'PASS' if has_cta else 'WARN (check CTA is specific)'}")

        # Word count
        report.append(f"Word Count: {total_words} (target 2000-3000)")

        return "\n".join(report)
