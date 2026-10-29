from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import json
import os


class WebResearchInput(BaseModel):
    """Input schema for the web research tool."""
    query: str = Field(..., description="The search query to research")
    country: str = Field(default="", description="The target country for context")


class WebResearchTool(BaseTool):
    name: str = "web_researcher"
    description: str = (
        "Performs a research lookup for a given topic and country. Query the tool with a "
        "research question (e.g., 'accounting automation statistics Malaysia'). Returns "
        "relevant search context from the environment when available, or a structured "
        "note that the agent should rely on domain knowledge and clearly mark estimates."
    )
    args_schema: Type[BaseModel] = WebResearchInput

    def _run(self, query: str, country: str = "") -> str:
        context = []

        # Check if there's a search API key configured
        serper_key = os.getenv("SERPER_API_KEY", "")

        context.append(f"Research Query: {query}")
        context.append(f"Target Country: {country}")

        if serper_key:
            try:
                import urllib.request
                import urllib.parse

                url = "https://google.serper.dev/search"
                payload = json.dumps({"q": query, "num": 5, "gl": "my"}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "X-API-KEY": serper_key,
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    results = data.get("organic", [])[:5]
                    context.append("\n=== SEARCH RESULTS ===")
                    for i, r in enumerate(results, 1):
                        context.append(f"{i}. {r.get('title', 'N/A')}")
                        context.append(f"   URL: {r.get('link', 'N/A')}")
                        context.append(f"   Snippet: {r.get('snippet', 'N/A')}\n")
            except Exception as e:
                context.append(f"\n[Search failed: {str(e)} — relying on domain knowledge and marking estimates]")
        else:
            context.append(
                "\n[No SERPER_API_KEY configured. Provide researched statistics from domain "
                "knowledge, always marking unverified numbers as 'estimated' or 'approximately'.]"
            )

        context.append(
            "\nResearch guidelines:\n"
            "- Provide specific numbers (percentages, hours, costs), not generic claims\n"
            "- Mark unverified data as (ESTIMATE)\n"
            "- Include region-specific data (tax rates, popular tools, pricing in local currency)\n"
            "- Focus on finance/accounting workflows (invoice processing, reconciliation, expenses)"
        )

        return "\n".join(context)
