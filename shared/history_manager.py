import os
import json
from typing import List, Dict, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

EXAM_UPDATE_HISTORY_PATH = os.path.join(PROJECT_ROOT, "history", "exam_updates_history.json")
EVERGREEN_HISTORY_PATH = os.path.join(PROJECT_ROOT, "history", "evergreen_content_history.json")

class HistoryManager:
    @staticmethod
    def load_exam_updates_history() -> List[Dict[str, Any]]:
        if not os.path.exists(EXAM_UPDATE_HISTORY_PATH):
            return []
        try:
            with open(EXAM_UPDATE_HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_exam_updates_history(entry: Dict[str, Any]):
        os.makedirs(os.path.dirname(EXAM_UPDATE_HISTORY_PATH), exist_ok=True)
        history = HistoryManager.load_exam_updates_history()
        history.append(entry)
        with open(EXAM_UPDATE_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_evergreen_history() -> List[Dict[str, Any]]:
        if not os.path.exists(EVERGREEN_HISTORY_PATH):
            return []
        try:
            with open(EVERGREEN_HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_evergreen_history(entry: Dict[str, Any]):
        os.makedirs(os.path.dirname(EVERGREEN_HISTORY_PATH), exist_ok=True)
        history = HistoryManager.load_evergreen_history()
        history.append(entry)
        with open(EVERGREEN_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
