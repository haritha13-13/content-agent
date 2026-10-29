#!/usr/bin/env python
import re
import sys
import warnings
import os

from pathlib import Path

# Ensure we can find the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from content_agent.crew import ContentGenerationCrew
from content_agent.helpers import keyword_slug

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

DEFAULT_KEYWORD = "AI AUTOMATION"
DEFAULT_COUNTRY = "COIMBATORE"
DEFAULT_INTERNALLINK = "/ai-invoice-processing"

# Target market currency for each published slug. Coimbatore/India articles are
# omitted -> they legitimately keep INR.
CURRENCY_BY_SLUG = {
    "ai-automation": "USD",
    "ai-invoice-processing": "SGD",
    "ai-bank-reconciliation": "SGD",
    "custom-link-test": "SGD",
    "bank-reconciliation-automation": "MYR",
    "expense-management-automation": "MYR",
    "ux-design": "MYR",
}
# Country/region -> currency fallback. "All over the world" / any other country
# (or an empty/global target) uses USD. India/Coimbatore keeps rupees (INR).
COUNTRY_CURRENCY = {
    "all over the world": "USD",
    "worldwide": "USD",
    "global": "USD",
    "malaysia": "MYR",
    "singapore": "SGD",
    "india": "INR",
    "coimbatore": "INR",
}
INR_PER_UNIT = {"USD": 0.1, "MYR": 0.05, "SGD": 0.06}  # 1 unit of each currency per INR (approx)


# ---------------------------------------------------------------- use cases ---
# Every blog must include a section about use cases specific to the target
# keyword. Topics are detected from the keyword slug; each topic maps to a
# set of (industry, outcome) bullets, localized per country region.
USE_CASE_TOPICS = {
    "invoice": {
        "coimbatore": [
            ("Textile manufacturing", "yarn purchase invoices, delivery challans, and GST returns auto-captured without re-typing"),
            ("MSMEs in Tamil Nadu", "vendor bills posted straight into Tally or Zoho Books with AI validation"),
            ("Engineering companies", "job invoices and purchase orders matched and routed for approval automatically"),
            ("Hospitals", "pharmacy supplier invoices captured and checked against purchase records before payment"),
            ("Educational institutions", "student fee and vendor invoices digitised with a full audit trail"),
            ("Inventory management", "goods-received notes checked against supplier invoices in real time"),
            ("AI invoice processing", "end-to-end capture, validation, and approval routing for every supplier bill"),
        ],
        "world": [
            ("Accounts payable teams", "supplier invoices captured and validated without manual data entry"),
            ("Manufacturing firms", "purchase orders matched against vendor bills before payment is released"),
            ("Retail and e-commerce", "high volumes of supplier invoices processed in minutes instead of days"),
            ("Healthcare providers", "medical supply invoices digitised and checked against purchase records"),
            ("Educational institutions", "vendor and fee invoices handled with a complete audit trail"),
            ("Logistics companies", "freight and vendor invoices reconciled quickly and routed for approval"),
            ("CFOs and finance leaders", "invoice processing errors and late-payment penalties sharply reduced"),
        ],
    },
    "reconciliation": {
        "coimbatore": [
            ("Textile manufacturing", "bank statements matched against vendor and customer ledgers automatically"),
            ("MSMEs in Tamil Nadu", "month-end lockout cleared in hours instead of weeks with AI matching"),
            ("Engineering companies", "job-wise receipts and payments reconciled to Tally and Zoho Books"),
            ("Hospitals", "insurance and pharmacy payment entries balanced against bank statements"),
            ("Educational institutions", "fee collections verified against bank deposits without manual checks"),
            ("Inventory management", "stock purchases cross-checked against supplier payments in real time"),
            ("AI bank reconciliation", "bank and ERP data pulled together for a single click-and-go match"),
        ],
        "world": [
            ("Finance teams", "bank statements matched against ERP ledgers automatically every day"),
            ("Retail and e-commerce", "card, bank, and wallet settlements reconciled at high volume"),
            ("Manufacturing firms", "payments and receipts balanced without end-of-month scrambling"),
            ("Healthcare providers", "payer and pharmacy payments matched against bank deposits"),
            ("Educational institutions", "fee collections reconciled against bank statements quickly"),
            ("Logistics companies", "customer payments and supplier settlements verified automatically"),
        ],
    },
    "expense": {
        "world": [
            ("Sales teams", "receipts captured on the go and claims auto-categorised"),
            ("Field service companies", "travel and fuel expenses submitted and approved from mobile"),
            ("Manufacturing firms", "supplier and operational expenses reconciled on time"),
            ("Retail and e-commerce", "operational spend tracked against budgets accurately"),
            ("CFOs and finance leaders", "spend visibility improved with real-time expense reporting"),
            ("Startups and SMEs", "expense policies enforced automatically at the point of claim"),
        ],
    },
    "ux": {
        "world": [
            ("Product teams", "user flows validated before costly development work begins"),
            ("SaaS companies", "conversion and onboarding experiences refined with research"),
            ("Mobile app startups", "navigation and sign-up flows designed for higher retention"),
            ("Marketing teams", "landing pages that turn visitors into leads"),
            ("Fintech and accounting software", "dashboards that users understand at first glance"),
        ],
    },
    "automation": {
        "coimbatore": [
            ("Textile manufacturing", "invoices, inventory, and payroll records digitised end to end"),
            ("MSMEs in Tamil Nadu", "repetitive finance tasks automated so founders focus on growth"),
            ("Engineering companies", "estimates, purchase orders, and job costing connected automatically"),
            ("Hospitals", "patient billing, pharmacy, and procurement workflows streamlined"),
            ("Educational institutions", "admissions, fees, and vendor payments automated with less effort"),
            ("Inventory management", "stock levels, re-orders, and supplier invoices kept in sync"),
            ("AI invoice processing", "invoices captured and routed with zero manual data entry"),
        ],
        "world": [
            ("Manufacturing firms", "production, procurement, and finance workflows linked automatically"),
            ("Retail and e-commerce", "orders, inventory, and payments processed without manual steps"),
            ("Healthcare", "patient and billing workflows streamlined across departments"),
            ("Education", "admissions, fees, and vendor payments handled efficiently"),
            ("Financial services", "back-office operations automated with fewer errors"),
            ("SaaS and tech companies", "internal ops and support processes scaled without adding headcount"),
        ],
    },
}

USE_CASE_DEFAULT_TOPIC = "automation"


def _use_case_topic(keyword: str) -> str:
    slug = keyword_slug(keyword)
    for topic, table in USE_CASE_TOPICS.items():
        if topic in slug:
            return topic
    return USE_CASE_DEFAULT_TOPIC


def _use_case_region(country: str) -> str:
    c = (country or "").strip().lower()
    if c in ("coimbatore", "tamil nadu", "india"):
        return "coimbatore"
    return "world"


def _use_case_bullets(keyword: str, country: str = "") -> list:
    topic = _use_case_topic(keyword)
    region = _use_case_region(country)
    table = USE_CASE_TOPICS.get(topic, USE_CASE_TOPICS[USE_CASE_DEFAULT_TOPIC])
    bullets = table.get(region) or table.get("world") or []
    if not bullets:
        bullets = USE_CASE_TOPICS[USE_CASE_DEFAULT_TOPIC]["world"]
    return bullets


def _enforce_use_cases(keyword: str, country: str = "") -> None:
    """Ensure the blog has a USE CASES section related to the target keyword.

    Inserts a "USE CASES FOR {KEYWORD}" section (with keyword-specific industry
    bullets, localized per country) when the writer omitted it or covered only
    a generic one.
    """
    slug = keyword_slug(keyword)
    path = Path("output") / "blogs" / f"{slug}.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    # Nothing to do if the writer already produced a keyword-related section.
    if re.search(r"(?im)^[A-Z0-9 &'()\-]*USE[ \t]+CASES", text):
        return

    heading = f"USE CASES FOR {keyword.upper()}"
    bullets = _use_case_bullets(keyword, country)
    lines = [heading, ""]
    for industry, outcome in bullets:
        lines.append(f"- {industry}: {outcome}.")
    block = "\n".join(lines) + "\n\n"

    # Insert after the "BEFORE AND AFTER" section (before "HOW TO GET STARTED").
    marker = re.search(r"(?im)^HOW[ \t]+TO[ \t]+GET[ \t]+STARTED", text)
    if marker:
        text = text[: marker.start()].rstrip() + "\n\n" + block + text[marker.start() :].lstrip("\n")
    else:
        text = text.rstrip() + "\n\n" + block
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------- article structure ---
# The blog can be built with any of several sub-topic structures, each applicable
# to every target keyword. The frontend lets the user pick one; when none is
# selected the AI generates its own structure (only USE CASES + FAQ stay mandatory).
DEFAULT_SUBTOPICS = "standard"

ARTICLE_STRUCTURES = {
    "standard": {
        "label": "Standard Workflow Guide",
        "prompt": (
            "Follow this EXACT 10-section structure. Each heading MUST appear as an ALL CAPS "
            "heading on its own line, in this order (replace {keyword}/{country} in the heading text):\n"
            '1. "WHAT IS {keyword}" — 80-120 words. Define the topic, include the primary keyword, '
            "mention Speedbots, state the value proposition.\n"
            '2. "THE HIDDEN COST OF MANUAL PROCESSES" — 300-500 words. 3-4 manual pain points with '
            "specific numbers (invoices per month, hours wasted, error rates). Use bullets. End "
            "positioning Speedbots as the fix.\n"
            '3. "USE CASES FOR {keyword}" — 250-400 words. 6-8 concrete industry-specific use cases '
            "related EXACTLY to '{keyword}'. Each bullet: '- Industry: what {keyword} does for them'. "
            "Use local industries when '{country}' is a specific region (e.g. textile manufacturing, "
            "MSMEs in Tamil Nadu, engineering companies, hospitals, educational institutions, "
            "inventory management, AI invoice processing); use worldwide industries (manufacturing, "
            "retail & e-commerce, healthcare, education, financial services, SaaS/tech) when "
            "'{country}' is 'All over the world'.\n"
            '4. "BEFORE AND AFTER: HOW AUTOMATION CHANGES YOUR WORKFLOW" — 400-600 words. 2-3 '
            "workflows, each with 'Before automation' (manual steps) and 'After automation with "
            "Speedbots' (automated steps), ending with time-saved metrics. Include an internal link.\n"
            '5. "HOW TO GET STARTED IN 6 STEPS" — 300-500 words. 6 numbered steps, step 1 is "Audit '
            'your current process." Include an internal link in step 3.\n'
            '6. "WHAT YOU PAY VS WHAT YOU SAVE" — 200-400 words. Cost breakdown (setup, subscription, '
            "per invoice) vs savings. End with net savings and payback period. Use USD when "
            "'{country}' is 'All over the world', otherwise the local currency.\n"
            '7. "STAYING IN CONTROL: RISKS AND SAFEGUARDS" — 200-400 words. 5 risks, each with a '
            "mitigation. Cover data accuracy, routing errors, integration failures, compliance, "
            "staff resistance.\n"
            '8. "REAL RESULTS FROM {country} BUSINESSES" — 200-300 words. Realistic company example '
            "with specific metrics (time reduction, error rate change, savings). Use \"REAL RESULTS "
            "FROM BUSINESSES\" (no country) when '{country}' is 'All over the world'. KEEP IT "
            "BELIEVABLE.\n"
            '9. "FREQUENTLY ASKED QUESTIONS" — 300-500 words. 6-8 numbered Q:/A: pairs. Answers '
            "specific to Speedbots capabilities.\n"
            '10. "START AUTOMATING YOUR PROCESSES" — 50-100 words. Specific CTA, e.g. "Book a free '
            'workflow assessment" or "Schedule a demo". Include the internal links from the strategy.'
        ),
        "headings": [
            r"^[A-Z0-9 &'()\-]*WHAT IS",
            r"^[A-Z0-9 &'()\-]*HIDDEN COST",
            r"^[A-Z0-9 &'()\-]*USE CASES",
            r"^[A-Z0-9 &'()\-]*BEFORE AND AFTER",
            r"^[A-Z0-9 &'()\-]*HOW TO GET STARTED",
            r"^[A-Z0-9 &'()\-]*WHAT YOU PAY",
            r"^[A-Z0-9 &'()\-]*STAYING IN CONTROL",
            r"FREQUENTLY ASKED QUESTIONS",
            r"START AUTOMATING",
        ],
    },
    "roi": {
        "label": "ROI & Business Case",
        "prompt": (
            "Follow this EXACT 9-section structure. Each heading MUST appear as an ALL CAPS heading "
            "on its own line, in this order (replace {keyword}/{country} in the heading text):\n"
            '1. "WHAT IS {keyword}" — 80-120 words. Define the topic, mention Speedbots, state value.\n'
            '2. "WHY {keyword} MATTERS NOW" — 200-300 words. Market drivers, pressure points, and '
            "statistics that make the case urgent.\n"
            '3. "THE BUSINESS CASE: COSTS VS SAVINGS" — 250-400 words. Setup, subscription, and '
            "per-unit costs vs measured savings. Use USD when '{country}' is 'All over the world', "
            "otherwise the local currency. Include a clear net-savings figure.\n"
            '4. "ROI CALCULATOR: HOW YOU RECOVER THE INVESTMENT" — 200-350 words. A worked example '
            "for a typical business: hours saved, error savings, cycle time, payback period.\n"
            '5. "COMPARISON: MANUAL VS AUTOMATED" — 200-300 words. A side-by-side comparison of '
            "time, cost, error rate, and compliance confidence.\n"
            '6. "INDUSTRY USE CASES & EXAMPLES" — 250-400 words. 6-8 industry-specific use cases of '
            "'{keyword}'. Use local industries when '{country}' is a specific region; worldwide "
            "industries when '{country}' is 'All over the world'.\n"
            '7. "COMMON PITFALLS AND HOW TO AVOID THEM" — 200-300 words. 4-6 pitfalls with mitigations.\n'
            '8. "FREQUENTLY ASKED QUESTIONS" — 300-500 words. 6-8 numbered Q:/A: pairs.\n'
            '9. "START AUTOMATING YOUR PROCESSES" — 50-100 words. Specific CTA and internal links.'
        ),
        "headings": [
            r"^[A-Z0-9 &'()\-]*WHAT IS",
            r"MATTERS NOW",
            r"BUSINESS CASE",
            r"ROI CALCULATOR",
            r"MANUAL VS AUTOMATED",
            r"INDUSTRY USE CASES",
            r"PITFALLS",
            r"FREQUENTLY ASKED QUESTIONS",
            r"START AUTOMATING",
        ],
    },
    "educational": {
        "label": "Educational Step-by-Step Guide",
        "prompt": (
            "Follow this EXACT 9-section structure. Each heading MUST appear as an ALL CAPS heading "
            "on its own line, in this order (replace {keyword}/{country} in the heading text):\n"
            '1. "WHAT IS {keyword}" — 80-120 words. Define the topic, mention Speedbots, state value.\n'
            '2. "HOW {keyword} WORKS UNDER THE HOOD" — 250-400 words. Explain the mechanics in plain '
            "language (capture, validation, routing, matching, reporting).\n"
            '3. "STEP-BY-STEP IMPLEMENTATION PLAN" — 300-500 words. Numbered steps from audit to go-live.\n'
            '4. "TOP FEATURES TO LOOK FOR IN A SOLUTION" — 200-350 words. A checklist of must-have '
            "capabilities to compare vendors.\n"
            '5. "INTEGRATIONS WITH YOUR EXISTING TOOLS" — 200-300 words. How it fits Tally, Zoho '
            "Books, QuickBooks, and bank APIs (use local tools when '{country}' is specific).\n"
            '6. "COMPLIANCE & SECURITY CONSIDERATIONS" — 200-300 words. Tax e-invoicing, data '
            "protection, audit trails, encryption.\n"
            '7. "REAL RESULTS FROM BUSINESSES" — 200-300 words. Realistic case-study metrics. Use '
            '"REAL RESULTS FROM {country} BUSINESSES" for a specific region.\n'
            '8. "FREQUENTLY ASKED QUESTIONS" — 300-500 words. 6-8 numbered Q:/A: pairs.\n'
            '9. "START AUTOMATING YOUR PROCESSES" — 50-100 words. Specific CTA and internal links.'
        ),
        "headings": [
            r"^[A-Z0-9 &'()\-]*WHAT IS",
            r"WORKS UNDER THE HOOD",
            r"STEP-BY-STEP IMPLEMENTATION",
            r"TOP FEATURES",
            r"INTEGRATIONS",
            r"COMPLIANCE & SECURITY",
            r"REAL RESULTS",
            r"FREQUENTLY ASKED QUESTIONS",
            r"START AUTOMATING",
        ],
    },
    "ai": {
        "label": "AI-Generated (auto)",
        "prompt": (
            "Design your OWN effective 6-8 section sub-topic structure that best serves '{keyword}' "
            "for the '{country}' target. Choose strong, keyword-specific ALL CAPS headings (do NOT "
            "copy the standard template). You MUST still include these two sections no matter what:\n"
            ' - "USE CASES FOR {keyword}" (6-8 industry-specific use cases)\n'
            ' - "FREQUENTLY ASKED QUESTIONS" (6-8 numbered Q:/A: pairs)\n'
            "Order the remaining sections sensibly for the topic, then end with a specific CTA "
            'section titled "START AUTOMATING YOUR PROCESSES". Use USD when \'{country}\' is '
            "'All over the world', otherwise the local currency."
        ),
        "headings": [
            r"^[A-Z0-9 &'()\-]*WHAT IS",
            r"^[A-Z0-9 &'()\-]*USE CASES",
            r"FREQUENTLY ASKED QUESTIONS",
            r"START AUTOMATING",
        ],
    },
    "basics": {
        "label": "Basics Guide (Beginner-Friendly)",
        "use_cases": False,
        "prompt": (
            "Write a BASICS GUIDE for '{keyword}' in the '{country}' market - plain, "
            "beginner-friendly information about the topic itself.\n"
            "KEYWORD RULE: use the keyword '{keyword}' VERBATIM - the same words in the same "
            "order - everywhere it appears. Never extend it (do not add words like 'automation', "
            "'AI', 'services' or 'solutions' to it) and never replace it with a synonym.\n"
            "SEO TITLE (the first line of the file, 3-55 characters): start with the exact "
            "keyword '{keyword}', then a natural beginner-guide hook shaped like "
            "'{keyword}: How to Choose the Perfect <X> for Your <Y>', where <X> and <Y> are the "
            "natural objects of the topic (for 'event function hall' that becomes "
            "'How to Choose the Perfect Venue for Your Event'). The keyword comes first and is "
            "never reworded.\n"
            "Then write these H2 sections as ALL CAPS headings, each on its own line, in this "
            "exact order. Start every heading with the quoted phrase, then complete it so it "
            "reads naturally for '{keyword}':\n"
            "1. \"WHAT IS\" - 80-120 words. Define '{keyword}' in plain language for a "
            "first-time reader: what it is, who it is for, what a good result looks like.\n"
            '2. "TYPES OF" - 200-350 words. The main types, categories or styles available for '
            "'{keyword}', with 5-7 bullets and one line each on who each type suits.\n"
            '3. "WHAT TO LOOK FOR IN" - 250-400 words. The facilities, features, specs and quality '
            "signals a buyer should check. Use a bullet checklist.\n"
            '4. "PRICING AND PACKAGES" - 200-350 words. Typical price ranges and what each package '
            "tier includes. Write the heading as \"{keyword} PRICING AND PACKAGES\". "
            "Plain reference information only.\n"
            '5. "HOW TO CHOOSE THE RIGHT" - 250-400 words. A practical selection guide: what to '
            "compare, what to avoid, which questions to ask before deciding.\n"
            "6. \"WHY CHOOSE OUR\" - 150-250 words. Why our offer is a good fit for "
            "'{keyword}', with concrete reasons.\n"
            '7. "FREQUENTLY ASKED QUESTIONS" - 300-500 words. 6-8 numbered Q:/A: pairs covering the '
            "basics a first-time buyer asks.\n"
            "Close with a short CTA paragraph (no extra heading) inviting the reader to talk to us.\n"
            "SCOPE RULE - this is a basics guide, so leave these OUT: cost-benefit analysis, ROI "
            "or payback, savings claims, a 'risks and safeguards' section, a list of industry use "
            "cases, and tax or compliance deep-dives. The pricing section is plain reference "
            "information (typical price ranges and what each package includes), not a business case."
        ),
        "headings": [
            r"^[A-Z0-9 &'()\-]*WHAT IS",
            r"^[A-Z0-9 &'()\-]*TYPES OF",
            r"^[A-Z0-9 &'()\-]*TO LOOK FOR",
            r"^[A-Z0-9 &'()\-]*(PRICING|PRICES) AND PACKAGES",
            r"^[A-Z0-9 &'()\-]*HOW TO CHOOSE THE RIGHT",
            r"^[A-Z0-9 &'()\-]*WHY CHOOSE OUR",
            r"FREQUENTLY ASKED QUESTIONS",
        ],
        "fallback_sections": {
            r"^[A-Z0-9 &'()\-]*WHAT IS": lambda kw, cc: (
                f"WHAT IS {kw.upper()}",
                f"{kw.capitalize()} is the subject of this guide. It covers the basics every "
                f"first-time buyer needs: what {kw.lower()} means, who it is for, what a good "
                "result looks like, and how the options compare. Read this section first if "
                f"{kw.lower()} is new to you.",
            ),
            r"^[A-Z0-9 &'()\-]*TYPES OF": lambda kw, cc: (
                f"TYPES OF {kw.upper()}",
                f"- The standard option: the simplest, most widely used form of {kw.lower()}.\n"
                f"- The mid-range option: more features, better support, a higher price.\n"
                f"- The premium option: the widest choice and the most customisation.\n"
                f"- The specialist option: built for one specific kind of {kw.lower()} need.\n"
                "- The budget option: covers the basics at the lowest price.",
            ),
            r"^[A-Z0-9 &'()\-]*TO LOOK FOR": lambda kw, cc: (
                f"WHAT TO LOOK FOR IN {kw.upper()}",
                f"- Quality and finish - check how {kw.lower()} holds up with regular use.\n"
                "- Capacity - it must fit the volume or size you actually need.\n"
                "- Support - what happens when something goes wrong after delivery.\n"
                "- Total cost - compare the full package price, not just the headline rate.\n"
                "- Reviews and references - ask for examples of similar work.\n"
                "- Terms - check what is included in the warranty or service agreement.",
            ),
            r"^[A-Z0-9 &'()\-]*(PRICING|PRICES) AND PACKAGES": lambda kw, cc: (
                f"{kw.upper()} PRICING AND PACKAGES",
                f"Packages for {kw.lower()} usually come in three tiers - basic, standard and "
                "premium. The basic tier covers the core requirement only. The standard tier adds "
                "the features most buyers need and is the most popular choice. The premium tier "
                "includes full customisation, priority support and the extras that only matter "
                "for larger operations. Ask for a written quote that lists every line item so you "
                "can compare like for like.",
            ),
            r"^[A-Z0-9 &'()\-]*HOW TO CHOOSE THE RIGHT": lambda kw, cc: (
                f"HOW TO CHOOSE THE RIGHT {kw.upper()}",
                "1. List your must-haves before you look at prices.\n"
                "2. Compare two or three options side by side on the same criteria.\n"
                "3. Read recent reviews and ask for references from similar buyers.\n"
                "4. Check the total cost, including delivery, setup and ongoing charges.\n"
                "5. Make sure the support and warranty terms match how you will use it.\n"
                "6. Choose the option that fits your volume today and can grow with you.",
            ),
            r"^[A-Z0-9 &'()\-]*WHY CHOOSE OUR": lambda kw, cc: (
                f"WHY CHOOSE OUR {kw.upper()}",
                f"We build {kw.lower()} for teams that want a dependable, straightforward result "
                "without the usual guesswork. Every package is explained in plain language before "
                "you commit, our pricing has no hidden extras, and the same team handles the "
                "handover, the training and the support afterwards. You get one point of contact "
                "for the whole process.",
            ),
            r"FREQUENTLY ASKED QUESTIONS": lambda kw, cc: (
                "FREQUENTLY ASKED QUESTIONS",
                f"1. What is {kw.lower()} in simple terms? It is the method that helps you get a "
                "predictable, repeatable result without relying on trial and error.\n"
                "2. How much does it usually cost? It depends on the package tier and the size of "
                "the job, so ask for a written quote.\n"
                "3. How long does it take? Most setups are running within one to two weeks.\n"
                "4. Can I change the package later? Yes, packages can be adjusted as your "
                "requirements change.\n"
                "5. What support do I get after delivery? Ongoing support, guidance and a direct "
                "contact for any question.\n"
                "6. Is it suitable for a small business? Yes, the basic package is built for "
                "smaller volumes.\n"
                "7. Do you deliver outside my city? Yes, we work with customers across the region.",
            ),
        },
    },
}


def _render_structure(structure: str, keyword: str, country: str = "") -> str:
    """Render the article-structure prompt for the chosen sub-topic set."""
    info = ARTICLE_STRUCTURES.get(structure) or ARTICLE_STRUCTURES[DEFAULT_SUBTOPICS]
    return info["prompt"].format(keyword=keyword, country=country)


def _use_cases_required(structure: str) -> bool:
    """Whether the chosen structure needs a dedicated USE CASES section."""
    info = ARTICLE_STRUCTURES.get(structure) or ARTICLE_STRUCTURES[DEFAULT_SUBTOPICS]
    return bool(info.get("use_cases", True))


def _use_cases_instruction(structure: str, keyword: str, country: str = "") -> str:
    """Strategy guidance for the USE CASES section (skipped by basics guides)."""
    if not _use_cases_required(structure):
        return (
            "SKIP USE CASES: this run is a basics guide. Do NOT produce a use-case list and do "
            "NOT create a USE CASES section."
        )
    return (
        f"Identify 6-8 concrete industry-specific USE CASES of '{keyword}' that apply to the "
        f"target: if '{country}' is a specific location/region (e.g. Coimbatore), use local "
        "industries (textile manufacturing, MSMEs in Tamil Nadu, engineering companies, hospitals, "
        "educational institutions, inventory management, AI invoice processing, etc.). If "
        f"'{country}' is \"All over the world\" or a non-specific global target, use worldwide "
        "industries (manufacturing, retail & e-commerce, healthcare, education, financial "
        "services, SaaS/tech, logistics). These use cases go in a dedicated USE CASES section."
    )


def _structure_rules(structure: str, keyword: str, country: str = "") -> str:
    """Structure-specific instructions shared by every task in the crew."""
    info = ARTICLE_STRUCTURES.get(structure) or ARTICLE_STRUCTURES[DEFAULT_SUBTOPICS]
    exact = (
        f"- Use the keyword '{keyword}' VERBATIM - same words, same order. Never add words to "
        "it (e.g. for 'event function hall' write 'Event Function Hall', NEVER 'Event Function "
        "Hall Automation')."
    )
    if info.get("use_cases", True):
        return (
            "STRUCTURE RULES FOR THIS RUN:\n"
            f"{exact}\n"
            "- Keep the section list from the SUB-TOPIC STRUCTURE exactly as given."
        )
    return (
        "STRUCTURE RULES FOR THIS RUN (basics guide):\n"
        f"{exact}\n"
        "- Do NOT create a USE CASES section and do NOT list industries or use cases.\n"
        "- Do NOT include cost-benefit analysis, ROI, payback period, savings claims, a risks "
        "and safeguards section, or tax/compliance deep-dives.\n"
        f"- The SEO title MUST start with the exact keyword '{keyword}' and follow "
        f"'{keyword}: How to Choose the Perfect <X> for Your <Y>'.\n"
        "- Every H2 heading starts with the exact phrase given in the structure and is then "
        "completed so it reads naturally for the topic.\n"
        "- Write beginner-friendly, factual information about the topic itself."
    )


_DEFAULT_SECTIONS = {
    r"^[A-Z0-9 &'()\-]*WHAT IS": lambda kw, cc: (
        f"WHAT IS {kw.upper()}",
        f"{kw.capitalize()} is the automated handling of {kw.lower()} tasks using AI, OCR, and "
        f"rule-based workflows. Speedbots applies this to capture, validate, route, and report so "
        f"your team stops re-keying data. The value is immediate: faster cycles, fewer errors, and a "
        f"clear return on investment from day one.",
    ),
    r"^[A-Z0-9 &'()\-]*HIDDEN COST": lambda kw, cc: (
        "THE HIDDEN COST OF MANUAL PROCESSES",
        "Manual workflows quietly drain budgets:\n"
        "- Hours lost re-typing data that could be automated.\n"
        "- 5%+ data-entry error rates that require expensive rework.\n"
        "- Delayed approvals that slow the whole finance cycle.\n"
        f"Speedbots removes these costs by automating {kw.lower()} end to end.",
    ),
    r"^[A-Z0-9 &'()\-]*USE CASES": lambda kw, cc: (
        f"USE CASES FOR {kw.upper()}",
        "- Manufacturing: invoices, inventory, and payroll records digitised end to end.\n"
        "- MSMEs: repetitive finance tasks automated so founders focus on growth.\n"
        "- Engineering: estimates, purchase orders, and job costing connected automatically.\n"
        "- Hospitals: patient billing, pharmacy, and procurement workflows streamlined.\n"
        "- Education: admissions, fees, and vendor payments automated with less effort.\n"
        "- Retail: supplier invoices and stock levels kept in sync.",
    ),
    r"^[A-Z0-9 &'()\-]*BEFORE AND AFTER": lambda kw, cc: (
        "BEFORE AND AFTER: HOW AUTOMATION CHANGES YOUR WORKFLOW",
        "Before automation, a document enters as paper or PDF, gets re-typed, emailed for approval, "
        f"and scheduled by hand - taking a full day. After automation with Speedbots, {kw.lower()} is "
        "captured in seconds, validated against rules, routed to the right approver, and the ledger "
        "updates in real time. Processing drops from 12 hours to 2 hours per document - an 83% saving.",
    ),
    r"^[A-Z0-9 &'()\-]*HOW TO GET STARTED": lambda kw, cc: (
        "HOW TO GET STARTED IN 6 STEPS",
        "1. Audit your current process and record cycle time, error rate, and cost.\n"
        "2. Set targets such as a 70% cycle-time cut and 90% fewer manual hours.\n"
        "3. Start with the highest-volume workflow.\n"
        "4. Run a small pilot and compare results against the baseline.\n"
        "5. Expand to more workflows while tuning validation rules.\n"
        "6. Train the team and share early wins so adoption sticks.",
    ),
    r"^[A-Z0-9 &'()\-]*WHAT YOU PAY": lambda kw, cc: (
        "WHAT YOU PAY VS WHAT YOU SAVE",
        f"Setup, a monthly subscription, and per-{kw.lower()} processing are modest. A mid-size "
        f"business typically saves 50 units per month in labor and rework. The payback lands around "
        f"the third month, with net savings reaching 6x the subscription by year one.",
    ),
    r"^[A-Z0-9 &'()\-]*STAYING IN CONTROL": lambda kw, cc: (
        "STAYING IN CONTROL: RISKS AND SAFEGUARDS",
        "1. Data Accuracy - mitigated with confidence thresholds and review queues.\n"
        "2. Routing Errors - mitigated with rule-based routing and fallback alerts.\n"
        "3. Integration Failures - mitigated with retry schedules and manual override.\n"
        "4. Compliance Gaps - mitigated with auto-filled fields and deadline flags.\n"
        "5. Staff Resistance - mitigated by positioning bots as handling repetitive work.",
    ),
    r"^[A-Z0-9 &'()\-]*REAL RESULTS": lambda kw, cc: (
        f"REAL RESULTS FROM {'ALL OVER THE WORLD' if cc and cc.lower() == 'all over the world' else cc} BUSINESSES",
        "A 60-employee company deployed Speedbots for a pilot batch. Cycle time fell from 5 days to "
        "1 day, the error rate dropped from 5% to 0.5%, and annual savings reached six figures. The "
        "business now closes its books a full week earlier each month.",
    ),
    r"MATTERS NOW": lambda kw, cc: (
        f"WHY {kw.upper()} MATTERS NOW",
        "Rising volumes, tighter deadlines, and shrinking margins make manual processing untenable. "
        f"Teams that adopt {kw.lower()} now cut costs, improve accuracy, and gain a competitive edge "
        "before their industry peers catch up.",
    ),
    r"BUSINESS CASE": lambda kw, cc: (
        "THE BUSINESS CASE: COSTS VS SAVINGS",
        f"Calibrating the numbers: setup cost is a one-time outlay; the subscription and "
        f"per-{kw.lower()} handling are recurring but small. Measured savings in labor, rework, and "
        "penalties typically exceed the total cost within a quarter, producing a clear net positive "
        "for the business.",
    ),
    r"ROI CALCULATOR": lambda kw, cc: (
        "ROI CALCULATOR: HOW YOU RECOVER THE INVESTMENT",
        "Worked example for a typical business: 1,000 documents a month, 7 hours per batch, a 5% "
        "error rate. Automating saves roughly 85% of manual hours and eliminates most rework. "
        "Payback lands around month three, and annual ROI comfortably exceeds 300%.",
    ),
    r"MANUAL VS AUTOMATED": lambda kw, cc: (
        "COMPARISON: MANUAL VS AUTOMATED",
        "- Time per document: days manually vs minutes automated.\n"
        "- Error rate: 5% manually vs under 0.5% automated.\n"
        "- Approval visibility: spreadsheet chase vs live audit trail.\n"
        "- Compliance: manual deadline tracing vs automatic statutory flags.",
    ),
    r"INDUSTRY USE CASES": lambda kw, cc: (
        "INDUSTRY USE CASES & EXAMPLES",
        "- Manufacturing: connects estimates, purchase orders, and job costing.\n"
        "- Retail & e-commerce: keeps supplier invoices and stock in sync.\n"
        "- Healthcare: streamlines patient billing and procurement.\n"
        "- Financial services: matches records and flags discrepancies in real time.\n"
        "- SaaS/tech: removes manual data entry for a lean finance team.",
    ),
    r"PITFALLS": lambda kw, cc: (
        "COMMON PITFALLS AND HOW TO AVOID THEM",
        "1. Automating a broken process first - fix the process, then automate.\n"
        "2. Skipping validation rules - misreads compound into errors.\n"
        "3. Poor integration handling - plan for API downtime.\n"
        "4. No change management - involve the team early.\n"
        "5. Ignoring compliance fields - keep statutory deadlines flagged.",
    ),
    r"WORKS UNDER THE HOOD": lambda kw, cc: (
        f"HOW {kw.upper()} WORKS UNDER THE HOOD",
        "In plain language: the system captures documents via OCR, validates them against business "
        "rules, routes them to the right approvers, matches them against records, and reports "
        "everything. Human review stays in place for low-confidence entries, so accuracy is "
        "controlled without slowing the flow.",
    ),
    r"STEP-BY-STEP IMPLEMENTATION": lambda kw, cc: (
        "STEP-BY-STEP IMPLEMENTATION PLAN",
        "1. Audit current workflows and define success metrics.\n"
        "2. Configure capture, validation, and routing rules.\n"
        "3. Integrate with Tally, Zoho Books, QuickBooks, and bank APIs.\n"
        "4. Run a pilot on a small batch and compare against baseline.\n"
        "5. Expand coverage and set up exception review queues.\n"
        "6. Train the team, go live, and monitor monthly ROI.",
    ),
    r"TOP FEATURES": lambda kw, cc: (
        "TOP FEATURES TO LOOK FOR IN A SOLUTION",
        "- OCR accuracy with confidence scoring.\n"
        "- Rule-based validation and approval routing.\n"
        "- Seamless ERP and bank API integrations.\n"
        "- Compliance fields (e-invoicing, audit trails).\n"
        "- Real-time dashboards and exception queues.",
    ),
    r"INTEGRATIONS": lambda kw, cc: (
        "INTEGRATIONS WITH YOUR EXISTING TOOLS",
        "Speedbots plugs into Tally, Zoho Books, QuickBooks, and major bank APIs. Data flows in "
        "from your existing systems and results write straight back to your ledgers - no duplicate "
        "entry, no export-import gymnastics.",
    ),
    r"COMPLIANCE & SECURITY": lambda kw, cc: (
        "COMPLIANCE & SECURITY CONSIDERATIONS",
        "Encryption at rest and in transit, role-based access, full audit trails, and automatic "
        "statutory deadline flags keep you compliant. Data stays segregated per tenant with "
        "ISO-aligned controls.",
    ),
    r"FREQUENTLY ASKED QUESTIONS": lambda kw, cc: (
        "FREQUENTLY ASKED QUESTIONS",
        "1. How fast is rollout? Live processing begins within two weeks.\n"
        "2. What formats are handled? PDFs, scanned images, and digital documents.\n"
        "3. Does it handle local tax fields? Yes - auto-filled and flagged before deadlines.\n"
        "4. Is my data secure? Encrypted, role-based, with full audit trails.\n"
        "5. Which tools does it connect to? Tally, Zoho Books, QuickBooks, and bank APIs.",
    ),
    r"START AUTOMATING": lambda kw, cc: (
        "START AUTOMATING YOUR PROCESSES",
        "Ready to launch? Book a free workflow assessment and see Speedbots in action. Schedule a "
        "demo now.",
    ),
}


def _heading_token(pattern: str) -> str:
    """Reduce a heading regex (and our section keys) to a plain upper-case token.

    '^[A-Z0-9 &'()\\-]*WHAT YOU PAY' -> 'WHAT YOU PAY'
    """
    s = pattern
    if s.startswith("^"):
        s = s[1:]
    close = s.rfind("]")
    if close >= 0:
        s = s[close + 1:]
    s = s.lstrip("*")
    return s.strip().upper()


def _match_builder(pattern: str, structure: str = ""):
    """Find the section builder for a heading pattern.

    A structure can ship its own generic fallback sections (used first); otherwise
    the global _DEFAULT_SECTIONS table is used.
    """
    info = ARTICLE_STRUCTURES.get(structure) or {}
    own = info.get("fallback_sections") or {}
    if pattern in own:
        return own[pattern]
    token = _heading_token(pattern)
    for key, builder in _DEFAULT_SECTIONS.items():
        if _heading_token(key) == token:
            return builder
    return None


def _enforce_subtopics(keyword: str, country: str = "", structure: str = "") -> None:
    """Ensure the blog contains every required heading of the chosen sub-topic set.

    Missing required headings are auto-inserted (deterministic fallback content derived
    from the structure) so the blog always conforms to the selected set instead of
    failing the whole job. Each missing section is inserted at its correct position in
    the structure's heading order.
    """
    if not structure:
        structure = DEFAULT_SUBTOPICS
    info = ARTICLE_STRUCTURES.get(structure) or ARTICLE_STRUCTURES[DEFAULT_SUBTOPICS]
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    headings = list(info["headings"])
    missing = [p for p in headings if not re.search(p, text, re.MULTILINE)]
    if not missing:
        return

    currency = _target_currency(keyword, country)
    currency_note = ""
    if currency == "USD":
        currency_note = " (USD figures apply - the target is All over the world)"
    elif currency:
        currency_note = f" All figures in {currency}."

    # Insert from the last missing section backwards so each one lands before the
    # first section that follows it in the declared order.
    for pattern in reversed(missing):
        builder = _match_builder(pattern, structure)
        if not builder:
            continue
        heading, body = builder(keyword, country)
        block = f"{heading}\n\n{body + currency_note}"

        anchor = None
        for later in headings[headings.index(pattern) + 1:]:
            m = re.search(later, text, re.MULTILINE)
            if m:
                anchor = m.start()
                break
        if anchor is None:
            text = text.rstrip() + "\n\n" + block + "\n"
        else:
            text = text[:anchor].rstrip() + "\n\n" + block + "\n\n" + text[anchor:].lstrip("\n")

    path.write_text(text, encoding="utf-8")


def _uppercase_required_headings(keyword: str, structure: str = "") -> None:
    """Upper-case heading lines so the DOCX renderer treats them as headings.

    The writer often keeps the keyword in title case inside an ALL CAPS heading
    ("WHAT IS Event function hall"), which would render as body text. Only short,
    punctuation-free lines that start with a required heading are normalised.
    """
    if not structure:
        structure = DEFAULT_SUBTOPICS
    info = ARTICLE_STRUCTURES.get(structure) or ARTICLE_STRUCTURES[DEFAULT_SUBTOPICS]
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        s = line.strip()
        if (
            s
            and len(s) <= 80
            and not re.search(r"[.!?,;]\s*$", s)
            and any(re.match(p, s) for p in info["headings"])
        ):
            upper = s.upper()
            if upper != line:
                changed = True
            out.append(upper)
        else:
            out.append(line)
    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _target_currency(keyword: str, country: str = "") -> str:
    """Resolve the currency for a keyword+country to a 3-letter code ('' = keep INR)."""
    slug = keyword_slug(keyword)
    if slug in CURRENCY_BY_SLUG:
        return CURRENCY_BY_SLUG[slug]
    return COUNTRY_CURRENCY.get((country or "").strip().lower(), "USD")


def run(keyword: str = DEFAULT_KEYWORD, country: str = DEFAULT_COUNTRY, internal_links: str = DEFAULT_INTERNALLINK,
        subtopics: str = DEFAULT_SUBTOPICS):
    """
    Run the content generation crew.
    Generates a full blog post with title, meta description, and internal links
    based on the Speedbots content strategy.
    `internal_links` is a comma/newline-separated list of URLs the writer should
    embed in the blog. ONLY these user-supplied links may appear in the blog;
    if empty, the blog gets NO internal links at all.
    `subtopics` selects which sub-topic structure the writer must follow
    ("standard" | "roi" | "educational" | "ai").
    """
    links_note = ""
    if internal_links and internal_links.strip():
        links_note = internal_links.strip()

    if not subtopics or subtopics not in ARTICLE_STRUCTURES:
        subtopics = DEFAULT_SUBTOPICS

    inputs = {
        'keyword': keyword,
        'country': country,
        'keyword_slug': keyword_slug(keyword),
        'internal_links': links_note,
        'subtopics': subtopics,
        'article_structure': _render_structure(subtopics, keyword, country),
        'structure_rules': _structure_rules(subtopics, keyword, country),
        'use_cases_instruction': _use_cases_instruction(subtopics, keyword, country),
    }

    print("=" * 60)
    print(f"Speedbots Content Generation Agent")
    print(f"Keyword: {keyword}")
    print(f"Country: {country}")
    print(f"Sub-topics structure: {subtopics}")
    print(f"Internal links: {links_note if links_note else '(none)'}")
    print("=" * 60)

    try:
        result = ContentGenerationCrew().crew().kickoff(inputs=inputs)
        _sanitize_blog(keyword)
        _enforce_exact_keyword(keyword)
        _enforce_title(keyword, subtopics)
        _enforce_country(keyword, country)
        _enforce_meta(keyword)
        _normalize_currency(keyword, country)
        if _use_cases_required(subtopics):
            _enforce_use_cases(keyword, country)
        _ensure_internal_links(keyword, links_note)
        _uppercase_required_headings(keyword, subtopics)
        _enforce_subtopics(keyword, country, subtopics)
        _verify_blog(keyword, country, subtopics)
        print("\n" + "=" * 60)
        print("CONTENT GENERATION COMPLETE")
        print("=" * 60)
        print(result)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def _sanitize_blog(keyword: str) -> None:
    """Remove duplicated blocks the writer sometimes emits.

    Some cloud-model runs repeat the SEO header block and/or the opening section
    (e.g. two META DESCRIPTION lines, or 'value-addedSEO TITLE: ...' glued onto
    the end of a paragraph). We keep the FIRST occurrence of each header line and
    the first occurrence of any repeated content line, and drop fragments that
    are clearly truncated repeats of already-present content.
    """
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    # 1) split header markers that were glued onto the end of the previous line
    for marker in ("SEO TITLE:", "META DESCRIPTION:", "CTA BUTTONS:"):
        text = re.sub(r"(?<!\n)\s*" + re.escape(marker), "\n" + marker, text)

    # 2) strip inline markdown bold markers (standalone **Heading** lines are kept)
    text = "\n".join(
        ln
        if not ("**" in ln and not (ln.strip().startswith("**") and ln.strip().endswith("**")))
        else ln.replace("**", "")
        for ln in text.splitlines()
    )

    lines = [ln.strip() for ln in text.splitlines()]

    def header_key(line: str):
        for k in ("SEO TITLE:", "META DESCRIPTION:", "CTA BUTTONS:"):
            if line.startswith(k):
                return k
        return None

    seen_headers = set()
    seen_content = set()
    out = []
    for line in lines:
        if not line:
            out.append("")
            continue
        k = header_key(line)
        if k is not None:
            if k in seen_headers:
                continue
            seen_headers.add(k)
            out.append(line)
            continue
        cf = line.casefold()
        if cf in seen_content:
            continue
        seen_content.add(cf)
        out.append(line)

    # drop non-punctuated fragments that are duplicates of longer kept lines
    final = []
    for line in out:
        if not line:
            final.append(line)
            continue
        cf = line.casefold()
        if not line.endswith((".", "!", "?", ":", ";", ",")) and len(line) > 5:
            if any(cf in other for other in seen_content if other != cf):
                continue
        final.append(line)

    text = "\n".join(final)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.lstrip("\n").rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


TOPONYMS = sorted([
    "United States", "USA", "United Kingdom", "UK", "United Arab Emirates", "UAE",
    "Australia", "Malaysia", "Singapore", "India", "Indonesia", "Vietnam",
    "Thailand", "Philippines", "Hong Kong", "Dubai", "Saudi Arabia", "Qatar",
    "Kuwait", "Oman", "Bahrain", "New Zealand", "Canada", "Germany", "France",
    "Netherlands", "Japan", "China", "South Korea", "South Africa", "Kenya",
    "Nigeria", "Tanzania", "Uganda", "Ghana", "Brazil", "Mexico", "Turkey",
    "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Myanmar",
], key=len, reverse=True)


def _enforce_country(keyword: str, country: str) -> None:
    """Ensure the SEO TITLE and META DESCRIPTION mention ONLY the input country.

    The model sometimes fills in Speedbots' default footprint (e.g. "Malaysia,
    Singapore, and Australia") even when a different country was requested. We
    strip any country/city name other than the requested one from these two lines.
    """
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return

    allowed = {country.strip().lower()} if country and country.strip() else set()
    names = [n for n in TOPONYMS if n.lower() not in allowed]

    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        if line.startswith(("SEO TITLE:", "META DESCRIPTION:")):
            cleaned = _strip_countries_from_line(line, names)
            if cleaned != line:
                changed = True
            out.append(cleaned)
        else:
            out.append(line)

    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _split_header(line: str):
    """Return (key, value) for SEO/meta lines, tolerating '**'/'#' prefixes.

    Also normalizes markdown-ish headers like '**META DESCRIPTION:** text'.
    Returns None when the line is not one of the three header markers.
    """
    m = re.match(r"^[*#\s]*(SEO TITLE:|META DESCRIPTION:|CTA BUTTONS:)[*#\s]*\s*(.*)$", line.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _enforce_country(keyword: str, country: str) -> None:
    """Ensure the SEO TITLE and META DESCRIPTION mention ONLY the input country.

    The model sometimes fills in Speedbots' default footprint (e.g. "Malaysia,
    Singapore, and Australia") even when a different country was requested. We
    strip any country/city name other than the requested one from these two lines.
    """
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return

    allowed = {country.strip().lower()} if country and country.strip() else set()
    names = [n for n in TOPONYMS if n.lower() not in allowed]

    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        h = _split_header(line)
        if h and h[0] in ("SEO TITLE:", "META DESCRIPTION:"):
            cleaned = _strip_countries_from_line(f"{h[0]} {h[1]}".strip(), names)
            if cleaned != line:
                changed = True
            out.append(cleaned)
        else:
            out.append(line)

    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _strip_countries_from_line(line: str, names) -> str:
    if not names:
        return line
    name_alt = "|".join(re.escape(n) for n in names)

    # 1) drop a whole "preposition + country list" phrase (e.g. "across Malaysia,
    #    Singapore, and Australia." or "for customers in India, UAE.")
    prep = (r"(?:across|in|for|to|covering|serving|lives in|located in|operations in|"
            r"businesses in|businesses across|markets in|customers in)")
    phr = re.compile(
        r"(?<![A-Za-z])" + prep + r"\s*((?:" + name_alt + r")(?:[,;\s]+(?:\s*and\s*)?(?:" + name_alt + r"))*)",
        re.IGNORECASE,
    )
    out, _ = phr.subn("", line)

    # 2) remove any standalone remaining country names (e.g. "in Bengaluru, India")
    singles = re.compile(r"(?<![\w])" + "(?:" + name_alt + r")" + r"(?![\w])", re.IGNORECASE)
    out, _ = singles.subn("", out)

    if out == line:
        return line

    # 3) tidy the punctuation artifacts left behind
    out = re.sub(r"\s*,\s*,+", ",", out)
    out = re.sub(r",\s+and\s*,+", ",", out)
    out = re.sub(r"\s*,(\s*$)", r"\1", out)
    out = re.sub(r"\s+and\s+$", "", out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\b(?:across|in|for|to|with|and|or|covering|serving)\s+[,.]", "", out)
    out = re.sub(r"\b(?:across|in|for|to|with|and|or|covering|serving)\s*$", "", out)
    out = re.sub(r",\s*\|", " |", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r"\s+\.", ".", out)
    out = out.lstrip(" ,;")
    if out.endswith(",") or out.endswith(";"):
        out = out[:-1].rstrip()
    out = re.sub(r"[ \t]+", " ", out).strip()
    return out


def _normalize_phrase(value: str) -> str:
    """Lower-case a phrase and reduce every non-alphanumeric run to a single space."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


def _has_keyword_phrase(text: str, keyword: str) -> bool:
    """Whether the text contains the whole keyword as a phrase."""
    kw = _normalize_phrase(keyword)
    return bool(kw) and kw in _normalize_phrase(text)


def _keyword_phrase_pattern(keyword: str) -> str:
    """Regex source matching the keyword as a phrase (tolerant of separators)."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", keyword or "") if w]
    if not words:
        return ""
    return r"[\s\-–—_]*".join(re.escape(w) for w in words)


def _enforce_exact_keyword(keyword: str) -> None:
    """Strip keyword extensions the writer invents (e.g. '<keyword> automation').

    The user's keyword must appear exactly as typed. When the keyword itself does
    not contain 'automation', every '<keyword> automation' phrase in the blog is
    rewritten back to the plain keyword (original casing preserved).
    """
    kw = (keyword or "").strip()
    if not kw or "automation" in kw.lower():
        return
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    phrase = _keyword_phrase_pattern(kw)
    if not phrase:
        return
    fixed = re.sub(rf"(?i)\b({phrase})[\s\-–—:&,]+automation\b", r"\1", text)
    if fixed != text:
        path.write_text(fixed, encoding="utf-8")


def _titlecase_keyword_prefix(title: str, keyword: str) -> str:
    """Title-case the keyword when it leads the title (keeps the rest untouched)."""
    phrase = _keyword_phrase_pattern(keyword)
    if not phrase:
        return title
    m = re.match(r"^\s*(" + phrase + r")", title, re.IGNORECASE)
    if not m:
        return title
    return _prettify_keyword(keyword) + title[m.end():]


def _enforce_title(keyword: str, structure: str = "") -> None:
    """Ensure the SEO TITLE is 3-55 characters and uses the keyword verbatim."""
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        h = _split_header(line)
        if h and h[0] == "SEO TITLE:":
            title = h[1].strip()
            if not _has_keyword_phrase(title, keyword):
                title = _fallback_title(keyword, structure)
            else:
                title = _titlecase_keyword_prefix(title, keyword)
            title = _shorten_title(title)
            new_line = f"SEO TITLE: {title}"
            if new_line != line:
                changed = True
            out.append(new_line)
        else:
            out.append(line)
    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _fallback_title(keyword: str, structure: str = "") -> str:
    """Deterministic title used when the writer's title misses the keyword phrase."""
    k = _prettify_keyword(keyword)
    if structure == "basics":
        return f"{k}: A Complete Beginner's Guide"
    return _standard_blog_title(keyword)


def _shorten_title(value: str, limit: int = 55) -> str:
    """Truncate a title to <= 55 characters at word boundaries, keeping context."""
    value = (value or "").strip()
    if len(value) <= limit:
        return value

    brand = ""
    if "|" in value:
        left, _, right = value.partition("|")
        right = right.strip()
        if "Speedbot" in right:
            brand = "Speedbots"
            value = left.strip()

    # drop generic filler words until it fits
    fillers = ["solutions", "solution", "for ", " in ", " the ", " and "]
    tokens = value.split()
    while len(" ".join(tokens)) > limit and len(tokens) > 2:
        changed = False
        for i, tok in enumerate(tokens[1:-1], 1):
            base = tok.strip(" ,-:").casefold()
            if base in (f.strip() for f in ("solutions", "solution")):
                del tokens[i]
                changed = True
                break
            if tok.strip(" ,-:") in ("in", "for") and len(tokens) > 3:
                del tokens[i]
                changed = True
                break
        if not changed:
            # drop the middle token
            del tokens[len(tokens) // 2]

    candidate = " ".join(tokens).strip(" ,-").strip()
    if len(candidate) <= limit - len(brand) - 3 and brand:
        candidate = f"{candidate} | {brand}"

    # hard fallback: word-boundary cut
    while len(candidate) > limit:
        candidate = candidate.rsplit(" ", 1)[0].rstrip(" ,-")
        if " " not in candidate:
            break
    return candidate[:limit].rstrip()


def _prettify_keyword(kw: str) -> str:
    """Title-case a keyword for generated SEO titles (keeps short acronyms upper)."""
    acronyms = {"AI", "UX", "AR", "VR", "SMS", "CRM", "ERP", "API", "ROI", "GST",
                "CNC", "HR", "IT", "SaaS", "RPA", "OCR", "NLP", "HTML", "CSS",
                "KPI", "POS", "POS"}
    stop = {"and", "of", "the", "for", "in", "with", "to", "a", "on", "at"}
    out = []
    for w in kw.split():
        u = w.upper()
        if u in acronyms:
            out.append(u)
        elif w.lower() in stop:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _standard_blog_title(keyword: str, limit: int = 55) -> str:
    """Deterministic 'keyword: benefit/topic' title (primary keyword once, natural)."""
    k = _prettify_keyword(keyword)
    candidates = [
        f"{k}: Benefits, Use Cases & Business Solutions",
        f"{k}: Benefits, Use Cases & Solutions",
        f"{k}: Benefits & Use Cases",
        f"{k}: Benefits & Guide",
        f"{k}: Benefits",
        k,
    ]
    for c in candidates:
        if len(c) <= limit:
            return c
    return candidates[-1][:limit].rsplit(" ", 1)[0]


def _retrofit_titles() -> None:
    """Rewrite all existing blog SEO titles to the 'keyword: benefit/topic' formula."""
    for p in (Path("output") / "blogs").glob("*.txt"):
        text = p.read_text(encoding="utf-8")
        if "SEO TITLE:" not in text:
            continue
        kw = p.stem.replace("-", " ")
        lines = text.splitlines()
        out = []
        for line in lines:
            h = _split_header(line)
            if h and h[0] == "SEO TITLE:":
                out.append("SEO TITLE: " + _standard_blog_title(kw))
            else:
                out.append(line)
        p.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _standard_meta_description(keyword: str, limit: int = 190) -> str:
    """Deterministic 'keyword + what it covers + benefit + optional CTA' meta (~150-165 chars)."""
    k = _prettify_keyword(keyword)
    candidates = [
        f"Discover how {k} helps businesses streamline repetitive tasks, improve productivity, "
        f"and build more efficient workflows. Explore practical use cases and solutions.",
        f"Discover how {k} helps businesses streamline tasks, improve productivity, "
        f"and build more efficient workflows. Explore use cases and solutions.",
        f"Discover how {k} helps businesses work faster, reduce errors, and scale. "
        f"Explore best practices and solutions.",
        f"Learn how {k} improves workflows and drives measurable results for growing teams.",
    ]
    for c in candidates:
        if len(c) <= limit:
            return c
    return candidates[-1]


def _retrofit_metas() -> None:
    """Rewrite all existing blog META DESCRIPTIONs to the keyword-first formula."""
    for p in (Path("output") / "blogs").glob("*.txt"):
        text = p.read_text(encoding="utf-8")
        if "META DESCRIPTION:" not in text:
            continue
        kw = p.stem.replace("-", " ")
        lines = text.splitlines()
        out = []
        for line in lines:
            h = _split_header(line)
            if h and h[0] == "META DESCRIPTION:":
                out.append("META DESCRIPTION: " + _standard_meta_description(kw))
            else:
                out.append(line)
        p.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _enforce_meta(keyword: str, limit: int = 190) -> None:
    """Trim an over-long META DESCRIPTION to <= 190 chars at a sentence boundary."""
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        h = _split_header(line)
        if h and h[0] == "META DESCRIPTION:":
            value = h[1].strip()
            if len(value) > limit:
                trimmed = value[:limit]
                cut = max(trimmed.rfind(". "), trimmed.rfind("! "), trimmed.rfind("? "))
                if cut != -1:
                    trimmed = trimmed[: cut + 1]
                new_line = f"META DESCRIPTION: {trimmed}"
                if new_line != line:
                    changed = True
                out.append(new_line)
            else:
                out.append(line)
        else:
            out.append(line)
    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _verify_blog(keyword: str, country: str = "", subtopics: str = "") -> None:
    """Ensure the blog file is an actual blog (has SEO TITLE/META/CTA top block).

    Also rejects files with a duplicated meta description line (repeats) and,
    when a country is given, any foreign country name inside the SEO/meta lines.
    """
    blog_path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not blog_path.exists():
        raise RuntimeError("Blog file was not created.")
    text = blog_path.read_text(encoding="utf-8")
    missing = [k for k in ("SEO TITLE:", "META DESCRIPTION:", "CTA BUTTONS:") if k not in text]
    if missing:
        raise RuntimeError(
            f"Blog file is not a valid blog (missing {', '.join(missing)}). "
            "The writer produced the wrong content; please regenerate."
        )
    n_meta = len(re.findall(r"^\s*META DESCRIPTION:", text, re.MULTILINE))
    if n_meta > 1:
        raise RuntimeError("Blog file has duplicate META DESCRIPTION lines; please regenerate.")

    tline = next((l for l in text.splitlines() if l.startswith("SEO TITLE:")), "")
    if tline:
        tvalue = tline.split("SEO TITLE:", 1)[1].strip()
        if not 3 <= len(tvalue) <= 55:
            raise RuntimeError(
                f"SEO TITLE length {len(tvalue)} is outside the allowed 3-55 characters: {tvalue[:80]}"
            )
        kwords = [w for w in re.sub(r"[^a-z0-9 ]", " ", keyword.lower()).split() if len(w) >= 3]
        if kwords and not any(
            re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", tvalue, re.IGNORECASE) for w in kwords
        ):
            raise RuntimeError(
                f"SEO TITLE does not contain the primary keyword ('{keyword}'): {tvalue[:80]}"
            )
        if not _has_keyword_phrase(tvalue, keyword):
            raise RuntimeError(
                f"SEO TITLE does not contain the full keyword phrase ('{keyword}'): {tvalue[:80]}"
            )
        # The keyword must be used exactly as given - no invented extensions.
        if "automation" not in keyword.lower():
            phrase = _keyword_phrase_pattern(keyword)
            if phrase and re.search(
                rf"(?i)\b({phrase})[\s\-–—:&,]+automation\b", tvalue
            ):
                raise RuntimeError(
                    f"SEO TITLE extends the keyword with 'automation': {tvalue[:80]}"
                )
    else:
        raise RuntimeError("Blog file has no SEO TITLE line; please regenerate.")

    allowed = {country.strip().lower()} if country and country.strip() else set()
    offenders = []
    for line in text.splitlines():
        if not line.startswith(("SEO TITLE:", "META DESCRIPTION:")):
            continue
        for name in TOPONYMS:
            if name.lower() in allowed:
                continue
            if re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", line, re.IGNORECASE):
                offenders.append(f"{line[:40]}... -> {name}")
    if offenders:
        raise RuntimeError(
            "SEO TITLE / META DESCRIPTION contain a foreign country name: "
            + "; ".join(sorted(set(offenders)))
        )

    mline = next((l for l in text.splitlines() if l.startswith("META DESCRIPTION:")), "")
    if mline:
        mvalue = mline.split("META DESCRIPTION:", 1)[1].strip()
        if not 100 <= len(mvalue) <= 200:
            raise RuntimeError(
                f"META DESCRIPTION length {len(mvalue)} is outside the 100-200 range: {mvalue[:80]}"
            )
        kw_phrase = re.sub(r"[^a-z0-9 ]", " ", keyword).strip().lower()
        kw_phrase = re.sub(r"\s+", " ", kw_phrase)
        if kw_phrase:
            hits = len(re.findall(re.escape(kw_phrase), mvalue.lower()))
            if hits > 2:
                raise RuntimeError(
                    f"META DESCRIPTION repeats the keyword '{keyword}' {hits} times (keyword stuffing)."
                )
            kwords = [w for w in kw_phrase.split() if len(w) >= 3]
            if kwords and not any(
                re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", mvalue, re.IGNORECASE)
                for w in kwords
            ):
                raise RuntimeError(
                    f"META DESCRIPTION does not contain the primary keyword ('{keyword}'): {mvalue[:80]}"
                )
        # meta must not be a copy of the blog's first sentence
        first_sentence = ""
        for l in text.splitlines():
            ls = l.strip()
            if ls and not ls.startswith(("SEO TITLE:", "META DESCRIPTION:", "CTA BUTTONS:")):
                first_sentence = ls
                break
        if first_sentence and mvalue.strip().casefold() == first_sentence.casefold():
            raise RuntimeError("META DESCRIPTION is a copy of the blog's first sentence.")

    slug = keyword_slug(keyword)
    currency = _target_currency(keyword, country)
    if currency and currency != "INR":
        # INR amounts are only valid for India/Coimbatore-targeted blogs.
        for line in text.splitlines():
            if re.search(r"₹|Rs\.?|(?i:\b(?:INR|Rupees?)\b)", line):
                raise RuntimeError(
                    f"Blog contains INR (₹) amounts but its target currency is {currency}: "
                    + line[:80]
                )

    # Every blog must include keyword-related use cases (unless the chosen
    # structure is a basics guide, which deliberately leaves them out).
    if _use_cases_required(subtopics) and not re.search(
        r"(?im)^[A-Z0-9 &'()\-]*USE[ \t]+CASES", text
    ):
        raise RuntimeError("Blog has no USE CASES section; please regenerate.")

    # The chosen sub-topic structure's headings must be present.
    if subtopics:
        _enforce_subtopics(keyword, country, subtopics)


def _normalize_currency(keyword: str, country: str = "") -> None:
    """Convert any INR (₹) amounts in a non-India market blog to the target currency.

    Only applies when the resolved currency is not INR. Coimbatore/India articles
    (INR) are skipped automatically.
    """
    slug = keyword_slug(keyword)
    currency = _target_currency(keyword, country)
    if not currency or currency == "INR":
        return
    blog_file = Path("output") / "blogs" / f"{slug}.txt"
    if not blog_file.exists():
        return
    text = blog_file.read_text(encoding="utf-8")
    if not re.search(r"₹|Rs\.?|(?i:\b(?:INR|Rupees?)\b)", text):
        return

    factor = INR_PER_UNIT[currency]
    new_chunks = []
    pos = 0
    for m in re.finditer(r"(?<![\w])(?:₹|INR\s*|Rs\.?\s*)([\d][\d,.]*)\s*(million|lakh|crore)?(?![\w])", text, re.IGNORECASE):
        new_chunks.append(text[pos:m.start()])
        amount = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        inr = amount * {"million": 1e6, "lakh": 1e5, "crore": 1e7}.get(unit, 1.0)
        converted = inr * factor
        sym = {"MYR": "RM", "SGD": "SGD", "USD": "USD"}[currency]
        if converted >= 1e6:
            new_chunks.append(f"{sym} {converted / 1e6:g} million")
        elif converted == int(converted):
            new_chunks.append(f"{sym} {int(converted):,}")
        else:
            new_chunks.append(f"{sym} {converted:,.2f}")
        pos = m.end()
    new_chunks.append(text[pos:])
    blog_file.write_text("".join(new_chunks), encoding="utf-8")


def _ensure_internal_links(keyword: str, internal_links: str) -> None:
    """Guarantee the generated blog contains ONLY the user's supplied internal links.

    - Only links typed in the internal-links box may appear (exact casing preserved).
    - If no links were supplied, ALL internal links are removed from the blog
      (the blog then has zero internal links).
    - Relative /paths are upgraded to full https://speedbots.com/ URLs.
    - If a supplied link is missing from the blog, it is INJECTED into the body.
    """
    blog_path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not blog_path.exists():
        return

    canonical = {}
    relative = {}
    for raw in (internal_links or "").replace(",", "\n").split():
        token = raw.strip().rstrip("/")
        if token.startswith("/"):
            token = "https://speedbots.com" + token
        if not token.startswith("http"):
            continue
        full = token
        canonical[full.lower()] = full
        if full.startswith("https://speedbots.com/"):
            rel = full.replace("https://speedbots.com", "")
            relative[rel.lower()] = full

    # If the user supplied NO links, strip EVERY URL from the blog (random URLs
    # invented by the writer are not allowed) and bail out.
    text = blog_path.read_text(encoding="utf-8")
    if not canonical:
        def strip_url(m):
            core, trailing = re.match(r"^(.*?)([.,;:!?)]*)$", m.group(0)).groups()
            return trailing or " "

        def strip_rel(m):
            path, trailing = re.match(r"^(/.*?)([.,;:!?)]*)$", m.group(1)).groups()
            if "-" in path or "_" in path:
                return " " + trailing or " "
            return m.group(0)

        cleaned = re.sub(r"https?://\S+", strip_url, text, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?<![A-Za-z0-9])(/[A-Za-z][A-Za-z0-9][^\s<),;'\"\]}.]*)", strip_rel, cleaned)
        # drop dangling "Link: ... at " / "Read more at " / "Dive deeper at " stubs left
        # over after the URL was removed (the writer attached a sentence to an empty link).
        def _is_link_stub(line):
            s = re.sub(r"[\-*_\[\]#]", "", line.strip())
            s = re.sub(r"\s+", " ", s).strip().rstrip(".").strip()
            return re.match(r"^(?:Link|Learn more|Read more|See more|Dive deeper)", s, re.I) and s.endswith(("at", "at .", "for more,"))
        cleaned = "\n".join(
            ln for ln in cleaned.splitlines() if not _is_link_stub(ln)
        )
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n ?\n+", "\n\n", cleaned)
        cleaned = re.sub(r"([,.;])\s*\)", r"\1", cleaned)
        blog_path.write_text(cleaned, encoding="utf-8")
        return

    # 1) normalize existing URLs: keep ONLY the user's supplied links (exact case),
    #    strip every other URL (any domain) the writer invented.
    allowed_lower = {u.lower() for u in canonical.values()}

    def normalize_abs(match):
        url = match.group(0)
        core, trailing = re.match(r"^(.*?)([.,;:!?)]*)$", url).groups()
        canonical_url = canonical.get(core.rstrip("/").lower())
        if canonical_url:
            return canonical_url + trailing
        return trailing or ""  # strip non-supplied URLs, keep trailing punct

    def normalize_rel(match):
        if match.group(1):
            return match.group(0)
        path, trailing = re.match(r"^(/.*?)([.,;:!?)]*)$", match.group(2)).groups()
        canonical_url = relative.get(path.rstrip("/").lower())
        if canonical_url:
            return canonical_url + trailing
        if "-" in path or "_" in path:
            return " " + trailing or " "
        return match.group(0)

    cleaned = re.sub(
        r"https?://\S+",
        normalize_abs,
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(https?://(?:www\.)?speedbots\.com)?(/[A-Za-z][A-Za-z0-9][^\s<),;'\"\]}.]*)",
        normalize_rel,
        cleaned,
    )
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n ?\n+", "\n\n", cleaned)
    cleaned = re.sub(r"([,.;])\s*\)", r"\1", cleaned)

    # 2) ensure EVERY allowed link is present; inject any that are missing
    allowed_urls = sorted(set(canonical.values()))
    missing = [u for u in allowed_urls if u.lower() not in cleaned.lower()]
    if missing:
        cleaned = cleaned.rstrip() + "\n\n"
        for i, url in enumerate(missing, 1):
            cleaned += f"Internal link {i}: Learn more about this at {url}\n"

    blog_path.write_text(cleaned, encoding="utf-8")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'keyword': DEFAULT_KEYWORD,
        'country': DEFAULT_COUNTRY,
        'keyword_slug': keyword_slug(DEFAULT_KEYWORD),
    }
    try:
        ContentGenerationCrew().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        ContentGenerationCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'keyword': DEFAULT_KEYWORD,
        'country': DEFAULT_COUNTRY,
        'keyword_slug': keyword_slug(DEFAULT_KEYWORD),
    }
    try:
        ContentGenerationCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


if __name__ == "__main__":
    run()
