import re
from typing import Dict, Any, List, Tuple

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

class DomainAdaptiveMasterclassAuditor:
    """
    High-Precision, High-Recall Domain-Adaptive Auditor for OdishaExamPrep Masterclasses.
    
    Balancing Architecture:
    1. Zero-Tolerance Invariants (100% Precision Guard against hallucinations, fake dates, and broken code).
    2. Domain-Adaptive Structural Windows (Prevents over-filtering on dense math/logic topics).
    3. Soft Gradient Scoring (Replaces rigid binary cliffs with proportional penalties).
    """

    FORBIDDEN_SPECULATIVE_PATTERNS = [
        r"\b(?:30|45|60|90)[\s-]day\s+(?:revision|crash|mastery|study|crack)\s+plan\b",
        r"\bopsc\s+(?:exam|prelims|mains)\s+is\s+scheduled\s+on\b",
        r"\bexpected\s+exam\s+date\s+is\b",
        r"\bofficial\s+notification\s+confirmed\s+for\s+(?:tomorrow|next\s+week)\b",
        r"\b(?:stay\s+positive|drink\s+plenty\s+of\s+water|wake\s+up\s+at\s+4\s*am|believe\s+in\s+yourself)\b",
        r"\bjust\s+work\s+hard\s+and\s+success\s+will\s+follow\b",
        r"\.{3,}$",  # Unfinished trailing sentences
    ]

    GENERIC_FILLER_PATTERNS = [
        r"\bin\s+conclusion\s*,\s*it\s+is\s+important\b",
        r"\bit\s+goes\s+without\s+saying\s+that\b",
        r"\bas\s+we\s+all\s+know\s*,\s*preparation\s+is\s+key\b",
        r"\bconsistency\s+is\s+the\s+ultimate\s+key\s+to\s+success\b"
    ]

    # Domain-Adaptive Word Count Floors (Prevents over-filtering on concise mathematical topics)
    DOMAIN_WORD_FLOORS = {
        "quantitative aptitude": 1150,
        "data interpretation": 1150,
        "logical reasoning": 1200,
        "language & grammar": 1200,
        "general studies & odisha gk": 1350,
        "test-taking strategy": 1250,
        "default": 1200
    }

    @classmethod
    def audit_article(cls, html_content: str, title: str, category: str) -> Dict[str, Any]:
        """
        Audits article using domain-aware thresholds and separated hard/soft guardrails.
        """
        critical_errors = []
        warnings = []
        score = 100

        if not html_content or len(html_content.strip()) < 250:
            return {
                "is_passed": False,
                "quality_score": 0,
                "word_count": 0,
                "critical_errors": ["Article content is critically empty or truncated."],
                "warnings": [],
                "stats": {}
            }

        if BeautifulSoup:
            soup = BeautifulSoup(html_content, "html.parser")
            plain_text = soup.get_text(separator=" ", strip=True)
            h2_tags = [h.get_text().strip() for h in soup.find_all("h2")]
            h3_tags = [h.get_text().strip() for h in soup.find_all("h3")]
            worked_examples = soup.find_all("div", class_=lambda c: c and "worked-example" in c.lower())
            tables_raw = soup.find_all("table")
            paragraphs_text = [p.get_text().strip() for p in soup.find_all("p")]
            faq_headers = soup.find_all(lambda tag: tag.name in ["h2", "h3", "h4"] and ("faq" in tag.get_text().lower() or "frequently asked" in tag.get_text().lower()))
            table_stats = []
            for t in tables_raw:
                table_stats.append({
                    "rows": len(t.find_all("tr")),
                    "has_thead": bool(t.find("thead") or t.find("th"))
                })
        else:
            plain_text = re.sub(r'<[^>]+>', ' ', html_content).strip()
            h2_tags = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content, re.I | re.DOTALL)
            h3_tags = re.findall(r'<h3[^>]*>(.*?)</h3>', html_content, re.I | re.DOTALL)
            worked_examples = re.findall(r'<div[^>]*class=["\'][^"\']*worked-example[^"\']*["\'][^>]*>', html_content, re.I)
            paragraphs_text = [re.sub(r'<[^>]+>', ' ', p).strip() for p in re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.I | re.DOTALL)]
            faq_headers = re.findall(r'<h[2-4][^>]*>(?:FAQ|Frequently Asked Questions).*?</h[2-4]>', html_content, re.I | re.DOTALL)
            tables_matches = re.findall(r'<table[^>]*>(.*?)</table>', html_content, re.I | re.DOTALL)
            table_stats = []
            for t_html in tables_matches:
                table_stats.append({
                    "rows": len(re.findall(r'<tr[^>]*>', t_html, re.I)),
                    "has_thead": bool(re.search(r'<thead|<th', t_html, re.I))
                })

        words = plain_text.split()
        word_count = len(words)
        cat_key = category.lower().strip()
        min_word_floor = cls.DOMAIN_WORD_FLOORS.get(cat_key, cls.DOMAIN_WORD_FLOORS["default"])

        # 1. Domain-Adaptive Word Count Evaluation
        if word_count < (min_word_floor - 150):
            critical_errors.append(f"Depth critically low: {word_count} words (Hard floor for {category}: {min_word_floor} words).")
            score -= 40
        elif word_count < min_word_floor:
            warnings.append(f"Word count slightly below optimal: {word_count} words (Recommended: {min_word_floor}+ words).")
            score -= 4
        elif word_count > 3400:
            warnings.append(f"Word count is high: {word_count} words.")
            score -= 2

        # 2. Heading Architecture (Soft Gradient Scoring)
        if len(h2_tags) < 3:
            critical_errors.append(f"Insufficient main sections: Found {len(h2_tags)} H2 headings (Minimum 3 required).")
            score -= 20
        elif len(h2_tags) < 4:
            warnings.append(f"Found {len(h2_tags)} H2 headings (Optimal: 4-6).")
            score -= 3

        if len(h3_tags) < 2:
            warnings.append(f"Found only {len(h3_tags)} H3 sub-headings.")
            score -= 3

        # 3. Micro-Paragraph Scannability
        dense_paragraphs = [len(p.split()) for p in paragraphs_text if len(p.split()) > 75]
        if len(dense_paragraphs) >= 3:
            warnings.append(f"Found {len(dense_paragraphs)} dense paragraphs (> 75 words).")
            score -= min(8, len(dense_paragraphs) * 2)

        # 4. Pedagogical Worked-Problem Breakdowns
        problem_keywords = len(re.findall(r"(?:Problem Statement|Exam Scenario|The Common Trap|Shortcut Algorithm|Final Answer)", plain_text, re.I))
        if not worked_examples and problem_keywords < 3:
            critical_errors.append("Missing required worked problem breakdowns with step-by-step algorithms.")
            score -= 30
        elif len(worked_examples) < 2 and problem_keywords < 5:
            warnings.append(f"Found {len(worked_examples)} worked example card (Optimal: 2).")
            score -= 4

        # 5. Comparison Table / Formula Matrix
        if not table_stats:
            critical_errors.append("Missing required custom reference/formula comparison table.")
            score -= 20
        else:
            for idx, t_info in enumerate(table_stats):
                if t_info["rows"] < 3:
                    warnings.append(f"Table #{idx+1} has only {t_info['rows']} rows.")
                    score -= 5
                if not t_info["has_thead"]:
                    warnings.append(f"Table #{idx+1} is missing header column labels.")
                    score -= 3

        # 6. Student FAQ Check
        q_count = len(re.findall(r"\bQ\d?[:\.]|\bQuestion[:\.]", plain_text))
        if not faq_headers and q_count < 2:
            warnings.append("Lacks a dedicated Student Dilemma FAQ section.")
            score -= 5

        # 7. ZERO-TOLERANCE INVARIANTS (100% Precision Filter against Noise)
        full_text_to_scan = f"{title} {html_content}"
        for pattern in cls.FORBIDDEN_SPECULATIVE_PATTERNS:
            match = re.search(pattern, full_text_to_scan, re.IGNORECASE)
            if match:
                critical_errors.append(f"HARD INVARIANT FAILURE: Forbidden speculative/fluff claim: '{match.group(0)}'.")
                score -= 50

        for filler in cls.GENERIC_FILLER_PATTERNS:
            match = re.search(filler, full_text_to_scan, re.IGNORECASE)
            if match:
                warnings.append(f"Detected generic cliché: '{match.group(0)}'.")
                score -= 3

        if re.search(r"\w+\.\.\.\s*$", plain_text) or "undefined" in html_content.lower():
            critical_errors.append("HARD INVARIANT FAILURE: Content truncated with '...' or contains undefined variables.")
            score -= 40

        # PLACEHOLDER CHECK: Drop any article containing unreplaced brackets like [Insert Number], [Topic Name]
        if re.search(r'\[(topic|exam|formula|concept|insert|name|category|date|amount|location)[^\]]*\]', full_text_to_scan, re.IGNORECASE):
            critical_errors.append("HARD INVARIANT FAILURE: Content contains unreplaced bracketed template placeholders.")
            score -= 50

        quality_score = max(0, min(100, score))
        is_passed = (len(critical_errors) == 0) and (quality_score >= 88)

        return {
            "is_passed": is_passed,
            "quality_score": quality_score,
            "word_count": word_count,
            "min_word_floor": min_word_floor,
            "critical_errors": critical_errors,
            "warnings": warnings,
            "stats": {
                "h2_count": len(h2_tags),
                "h3_count": len(h3_tags),
                "tables_count": len(table_stats),
                "worked_examples_count": len(worked_examples),
                "dense_paragraphs": len(dense_paragraphs)
            }
        }

# Aliases for backward compatibility
IroncladMasterclassAuditor = DomainAdaptiveMasterclassAuditor
BlogQualityLinter = DomainAdaptiveMasterclassAuditor
