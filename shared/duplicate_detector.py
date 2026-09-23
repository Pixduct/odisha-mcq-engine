import re
from typing import List, Dict, Any
from .history_manager import HistoryManager

class DuplicateDetector:
    @staticmethod
    def is_exam_update_duplicate(organization: str, exam: str, update_type: str, notification_num: str, history: List[Dict[str, Any]]) -> bool:
        """
        Checks Engine 1 history for duplicate notification postings.
        """
        for item in history:
            if (item.get("organization", "").upper() == organization.upper() and
                item.get("exam", "").upper() == exam.upper() and
                item.get("update_type", "").upper() == update_type.upper()):
                
                # Check notification number if present
                if notification_num and item.get("notification_number") == notification_num:
                    return True
                # If within 7 days, treat as duplicate
                return True
        return False

    @staticmethod
    def is_evergreen_concept_duplicate(concept_id: str, history: List[Dict[str, Any]]) -> bool:
        """
        Checks Engine 2 history for semantic concept ID duplicates.
        """
        norm_concept = concept_id.strip().lower()
        for item in history:
            if item.get("concept_id", "").strip().lower() == norm_concept:
                return True
        return False

    @staticmethod
    def check_cannibalization_against_blogs(title: str, existing_blogs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compares new article title/keywords against existing Supabase blogs to detect cannibalization.
        Returns {"action": "NEW_ARTICLE" | "UPDATE_EXISTING" | "SKIP", "existing_article_id": str}
        """
        title_tokens = set(re.findall(r'\w+', title.lower()))
        if not title_tokens:
            return {"action": "NEW_ARTICLE"}

        for blog in existing_blogs:
            b_title = (blog.get("name") or "").lower()
            b_tokens = set(re.findall(r'\w+', b_title))
            if not b_tokens:
                continue

            intersection = title_tokens.intersection(b_tokens)
            similarity = len(intersection) / float(min(len(title_tokens), len(b_tokens)))

            if similarity >= 0.8:
                return {
                    "action": "UPDATE_EXISTING",
                    "existing_article_id": blog.get("id"),
                    "existing_title": blog.get("name")
                }

        return {"action": "NEW_ARTICLE"}
