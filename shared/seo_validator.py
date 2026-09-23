import re
from typing import Dict, Any

class SEOValidator:
    GENERIC_BLACKLIST = [
        "competitive exams are becoming increasingly difficult",
        "many students struggle with preparation",
        "success requires hard work and dedication",
        "believe in yourself",
        "hard work is the key to success",
        "stay consistent and never give up",
        "in today's competitive world"
    ]

    @staticmethod
    def validate_article(article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates technical SEO, depth, actionability, tables, checklists, and calculates 100-point score.
        """
        title = article.get("title", "").strip()
        html = article.get("html_content", "").strip()
        slug = article.get("slug", "").strip()
        content_type = article.get("content_type", "EVERGREEN_EDUCATIONAL")

        # Strip any duplicate <h1> tags from html body (title serves as single H1)
        h1_matches = re.findall(r'<h1[^>]*>.*?</h1>', html, flags=re.IGNORECASE | re.DOTALL)
        if len(h1_matches) > 0:
            html = re.sub(r'<h1[^>]*>.*?</h1>', '', html, flags=re.IGNORECASE | re.DOTALL).strip()

        # Clean slug formatting
        clean_slug = re.sub(r'[^a-z0-9\-]', '', slug.lower().replace(' ', '-'))
        clean_slug = re.sub(r'-+', '-', clean_slug).strip('-')

        article["html_content"] = html
        article["slug"] = clean_slug

        # Word count calculation (strip HTML tags)
        plain_text = re.sub(r'<[^>]*>', ' ', html)
        words = plain_text.split()
        word_count = len(words)
        article["word_count"] = word_count

        # Detailed 100-Point Quality Evaluation
        usefulness_score = 20
        specificity_score = 15
        actionability_score = 15
        research_score = 15
        search_intent_score = 10
        originality_score = 10
        readability_score = 5
        internal_linking_score = 5
        seo_fundamentals_score = 5

        # Check word count depth against content_type target
        if content_type == "EXAM_UPDATE":
            if word_count < 500:
                specificity_score -= 8
                actionability_score -= 8
        else: # EVERGREEN_EDUCATIONAL
            if word_count < 1000:
                usefulness_score -= 10
                specificity_score -= 10
                actionability_score -= 10
            elif word_count < 1400:
                usefulness_score -= 5
                specificity_score -= 5

        # Check for tables or error log frameworks
        if "<table" not in html.lower() and "|" not in html:
            specificity_score -= 5
            actionability_score -= 5

        # Check for checklists / action plans
        if "checklist" not in html.lower() and "action plan" not in html.lower() and "[ ]" not in html:
            actionability_score -= 5

        # Check for generic blacklisted motivational phrases
        lower_html = html.lower()
        has_generic = any(phrase in lower_html for phrase in SEOValidator.GENERIC_BLACKLIST)
        if has_generic:
            originality_score -= 8
            usefulness_score -= 8

        # SEO fundamentals check
        if len(title) < 15 or len(title) > 90:
            seo_fundamentals_score -= 2
        if len(article.get("meta_description", "")) < 50:
            seo_fundamentals_score -= 2
        if "<h2>" not in html.lower():
            seo_fundamentals_score -= 1

        total_score = (
            max(0, usefulness_score) +
            max(0, specificity_score) +
            max(0, actionability_score) +
            max(0, research_score) +
            max(0, search_intent_score) +
            max(0, originality_score) +
            max(0, readability_score) +
            max(0, internal_linking_score) +
            max(0, seo_fundamentals_score)
        )

        article["seo_score"] = min(100, max(0, total_score))
        return article
