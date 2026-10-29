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
    "ai-automation": "MYR",
    "ai-invoice-processing": "SGD",
    "ai-bank-reconciliation": "SGD",
    "custom-link-test": "SGD",
    "bank-reconciliation-automation": "MYR",
    "expense-management-automation": "MYR",
    "ux-design": "MYR",
}
INR_PER_UNIT = {"MYR": 0.05, "SGD": 0.06}  # 1 MYR ~ 0.05x INR; 1 SGD ~ 0.06x INR (approx)


def run(keyword: str = DEFAULT_KEYWORD, country: str = DEFAULT_COUNTRY, internal_links: str = DEFAULT_INTERNALLINK):
    """
    Run the content generation crew.
    Generates a full blog post with title, meta description, and internal links
    based on the Speedbots content strategy.
    `internal_links` is a comma/newline-separated list of URLs the writer should
    embed in the blog. ONLY these user-supplied links may appear in the blog;
    if empty, the blog gets NO internal links at all.
    """
    links_note = ""
    if internal_links and internal_links.strip():
        links_note = internal_links.strip()

    inputs = {
        'keyword': keyword,
        'country': country,
        'keyword_slug': keyword_slug(keyword),
        'internal_links': links_note,
    }

    print("=" * 60)
    print(f"Speedbots Content Generation Agent")
    print(f"Keyword: {keyword}")
    print(f"Country: {country}")
    print(f"Internal links: {links_note if links_note else '(none)'}")
    print("=" * 60)

    try:
        result = ContentGenerationCrew().crew().kickoff(inputs=inputs)
        _sanitize_blog(keyword)
        _enforce_title(keyword)
        _enforce_country(keyword, country)
        _enforce_meta(keyword)
        _normalize_currency(keyword)
        _ensure_internal_links(keyword, links_note)
        _verify_blog(keyword, country)
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


def _enforce_title(keyword: str) -> None:
    """Ensure the SEO TITLE is 3-55 characters (the visible title value)."""
    path = Path("output") / "blogs" / f"{keyword_slug(keyword)}.txt"
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    changed = False
    out = []
    for line in lines:
        h = _split_header(line)
        if h and h[0] == "SEO TITLE:":
            title = _shorten_title(h[1])
            new_line = f"SEO TITLE: {title}"
            if new_line != line:
                changed = True
            out.append(new_line)
        else:
            out.append(line)
    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


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


def _verify_blog(keyword: str, country: str = "") -> None:
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
    currency = CURRENCY_BY_SLUG.get(slug)
    if currency:
        # Title/META must never carry INR for a non-India market.
        for line in text.splitlines():
            if re.search(r"₹|Rs\.?|(?i:\b(?:INR|Rupees?)\b)", line):
                raise RuntimeError(
                    f"Blog contains INR (₹) amounts but its target currency is {currency}: "
                    + line[:80]
                )


def _normalize_currency(keyword: str) -> None:
    """Convert any INR (₹) amounts in a non-India market blog to the target currency.

    Only applies to slugs listed in CURRENCY_BY_SLUG (MYR/SGD markets). Coimbatore
    (India) articles keep INR, so they are skipped automatically.
    """
    slug = keyword_slug(keyword)
    currency = CURRENCY_BY_SLUG.get(slug)
    if not currency:
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
        sym = "RM" if currency == "MYR" else "SGD"
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

    text = blog_path.read_text(encoding="utf-8")

    # 1) normalize existing URLs (full -> exact case; relative path -> full URL)
    def normalize_abs(match):
        url = match.group(0)
        core, trailing = re.match(r"^(.*?)([.,;:!?)]*)$", url).groups()
        canonical_url = canonical.get(core.rstrip("/").lower())
        if canonical_url:
            return canonical_url + trailing
        return ""

    def normalize_rel(match):
        if match.group(1):
            return match.group(0)
        path, trailing = re.match(r"^(/.*?)([.,;:!?)]*)$", match.group(2)).groups()
        canonical_url = relative.get(path.rstrip("/").lower())
        if canonical_url:
            return canonical_url + trailing
        if "-" in path or "_" in path:
            return ""
        return match.group(0)

    cleaned = re.sub(
        r"https?://(?:www\.)?speedbots\.com/[^\s<),;'\"\]}]+",
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
