import re
from typing import Dict, Any, List

EXAM_VISUAL_CONTEXT = {
    "OSSSC Nursing Officer": {
        "primary_context": ["nursing", "healthcare", "clinical education", "nursing student", "nurse", "hospital", "patient care"],
        "preferred_visuals": [
            "Indian nursing student studying clinical nursing textbooks",
            "nursing student with medical textbooks in library",
            "nursing student clinical training healthcare",
            "Indian nurse in healthcare setting studying",
            "nursing education medical study"
        ],
        "avoid": ["furniture", "living room", "generic western university student", "engineering student", "office worker"]
    },
    "OSSC CGL": {
        "primary_context": ["competitive exam", "government job preparation", "graduate-level exam", "aptitude", "reasoning", "mock test", "study"],
        "preferred_visuals": [
            "Indian competitive exam aspirant studying for OSSC",
            "Indian student preparing for government exam notes",
            "Indian student solving aptitude problems pen paper",
            "competitive exam preparation desk study",
            "student taking online mock test laptop notes"
        ],
        "avoid": ["furniture", "living room", "nursing", "hospital", "engineering laboratory"]
    },
    "OSSSC CTSRE": {
        "primary_context": ["engineering", "technical education", "technical subjects", "engineering students", "laboratory", "technical preparation"],
        "preferred_visuals": [
            "Indian engineering students studying technical subjects",
            "engineering student technical laboratory study",
            "engineering students working on technical project",
            "technical education engineering student",
            "engineering exam preparation books"
        ],
        "avoid": ["furniture", "living room", "nursing", "hospital", "generic medical student"]
    },
    "OPSC": {
        "primary_context": ["civil services", "government examination", "public administration", "serious study"],
        "preferred_visuals": [
            "Indian civil services aspirant studying in library",
            "Indian government exam aspirant studying reference books",
            "competitive exam preparation serious study desk"
        ],
        "avoid": ["furniture", "living room", "nursing", "engineering laboratory"]
    },
    "Railway Exams": {
        "primary_context": ["railway recruitment", "government job", "competitive examination", "CBT preparation"],
        "preferred_visuals": [
            "Indian railway exam aspirant studying",
            "Indian competitive exam student online study",
            "student preparing for railway recruitment exam notes"
        ],
        "avoid": ["furniture", "living room", "nursing", "medical setting"]
    },
    "SSC Exams": {
        "primary_context": ["competitive examination", "government job", "quantitative aptitude", "reasoning"],
        "preferred_visuals": [
            "Indian SSC aspirant studying for exam",
            "Indian competitive exam preparation desk notes",
            "student solving quantitative aptitude problems"
        ],
        "avoid": ["furniture", "living room", "nursing", "engineering laboratory"]
    },
    "Banking Exams": {
        "primary_context": ["banking", "competitive examination", "quantitative aptitude", "financial awareness"],
        "preferred_visuals": [
            "Indian banking exam aspirant studying",
            "student preparing for banking exam online desk",
            "Indian student studying quantitative aptitude notes"
        ],
        "avoid": ["furniture", "living room", "nursing", "hospital setting"]
    }
}

def infer_exam_visual_context(target_exam: str, title: str = "", category: str = "") -> Dict[str, Any]:
    """
    Dynamically infers visual context for any exam (Odisha/Central/SSC/Railway/Banking/Defence/Teaching).
    """
    exam_clean = target_exam.strip()
    
    # Direct match in configuration
    for key, ctx in EXAM_VISUAL_CONTEXT.items():
        if key.lower() in exam_clean.lower() or exam_clean.lower() in key.lower():
            return ctx

    combined = f"{exam_clean} {title} {category}".lower()

    # Dynamic Inference
    if any(k in combined for k in ["nursing", "nurse", "pharmacology", "medical", "clinical", "hospital", "aiims"]):
        return EXAM_VISUAL_CONTEXT["OSSSC Nursing Officer"]
    elif any(k in combined for k in ["technical", "ctsre", "engineering", "engineer", "mechanical", "electrical", "civil", "je", "alp"]):
        return EXAM_VISUAL_CONTEXT["OSSSC CTSRE"]
    elif any(k in combined for k in ["opsc", "civil services", "ias", "oas", "psc"]):
        return EXAM_VISUAL_CONTEXT["OPSC"]
    elif any(k in combined for k in ["railway", "rrb", "ntpc", "group d"]):
        return EXAM_VISUAL_CONTEXT["Railway Exams"]
    elif any(k in combined for k in ["ssc", "chsl", "cgl", "mts"]):
        return EXAM_VISUAL_CONTEXT["SSC Exams"]
    elif any(k in combined for k in ["bank", "ibps", "sbi", "po", "clerk"]):
        return EXAM_VISUAL_CONTEXT["Banking Exams"]
    elif any(k in combined for k in ["teacher", "ctet", "otet", "teaching"]):
        return {
            "primary_context": ["teaching", "education", "classroom"],
            "preferred_visuals": ["Indian teacher training classroom", "student preparing for teaching exam"],
            "avoid": ["furniture", "living room", "nursing", "engineering laboratory"]
        }
    elif any(k in combined for k in ["police", "si", "constable", "defence"]):
        return {
            "primary_context": ["police", "recruitment", "government job"],
            "preferred_visuals": ["Indian police exam aspirant studying", "government recruitment exam aspirant"],
            "avoid": ["furniture", "living room", "nursing", "hospital"]
        }
    else:
        # Default OSSC CGL General Govt Exam context
        return EXAM_VISUAL_CONTEXT["OSSC CGL"]

def build_smart_exam_visual_query(title: str, category: str, target_exam: str, content_type: str = "EVERGREEN_EDUCATIONAL") -> Dict[str, Any]:
    """
    Combines EXAM CONTEXT + ARTICLE SUBJECT + REAL-WORLD ACTIVITY into a specific photographic query.
    """
    context = infer_exam_visual_context(target_exam, title, category)
    lower_title = title.lower()
    
    # Detect Article Subject & Activity
    activity_query = ""
    if "mock test" in lower_title or "analysis" in lower_title or "score" in lower_title:
        activity_query = "analyzing mock test results answers notebook"
    elif "pharmacology" in lower_title or "drug" in lower_title:
        activity_query = "studying pharmacology textbook notes"
    elif "quantitative" in lower_title or "quant" in lower_title or "math" in lower_title or "calculation" in lower_title:
        activity_query = "solving quantitative aptitude math problems pen paper"
    elif "reasoning" in lower_title:
        activity_query = "solving reasoning puzzle questions notebook"
    elif "revision" in lower_title or "routine" in lower_title or "plan" in lower_title:
        activity_query = "studying revision schedule books desk"
    elif content_type == "EXAM_UPDATE" or "notification" in lower_title or "recruitment" in lower_title:
        activity_query = "reviewing official government recruitment exam announcement document"

    # Select base visual template
    base_visual = context["preferred_visuals"][0]
    
    if activity_query:
        # Combine: Indian [profession] aspirant + activity
        if "nursing" in context["primary_context"]:
            primary_search_query = f"Indian nursing student {activity_query}"
        elif "engineering" in context["primary_context"]:
            primary_search_query = f"Indian engineering student {activity_query}"
        else:
            primary_search_query = f"Indian competitive exam student {activity_query}"
    else:
        primary_search_query = base_visual

    search_queries = [primary_search_query] + context["preferred_visuals"]

    return {
        "primary_query": primary_search_query,
        "search_queries": search_queries,
        "primary_context": context["primary_context"],
        "avoid_keywords": context["avoid"]
    }
