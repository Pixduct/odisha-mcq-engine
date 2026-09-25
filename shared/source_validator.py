import os
import json
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOMATIONS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
TRUSTED_SOURCES_PATH = os.path.join(AUTOMATIONS_ROOT, "config", "trusted_sources.json")

def load_trusted_sources():
    if os.path.exists(TRUSTED_SOURCES_PATH):
        try:
            with open(TRUSTED_SOURCES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading trusted_sources.json: {e}")
    return {
        "official_domains": [
            "osssc.gov.in", "ossc.gov.in", "opsc.gov.in", "odishapolice.gov.in",
            "ssbodisha.ac.in", "ssbodisha.site", "bseodisha.ac.in", "oav.edu.in",
            "orissahighcourt.nic.in", "ssc.gov.in", "ssc.nic.in", "rrbcdg.gov.in",
            "rrbbbs.gov.in", "rrbapply.gov.in", "indianrailways.gov.in", "upsc.gov.in",
            "upsconline.nic.in", "ibps.in", "sbi.co.in", "rbi.org.in", "nta.ac.in"
        ],
        "trusted_educational_domains": ["testbook.com", "adda247.com", "pw.live"],
        "untrusted_social_domains": ["youtube.com", "t.me", "facebook.com"]
    }

class SourceValidator:
    def __init__(self):
        self.sources = load_trusted_sources()

    def is_official_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        if not domain and "://" not in url:
            domain = url.split("/")[0].lower()
        # Direct check for official sovereign and statutory TLD suffixes in India
        if domain.endswith(".gov.in") or domain.endswith(".nic.in") or domain.endswith(".res.in"):
            return True
        return any(off in domain for off in self.sources.get("official_domains", []))

    def is_trusted_educational_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(edu in domain for edu in self.sources.get("trusted_educational_domains", []))

    def is_untrusted_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(un in domain for un in self.sources.get("untrusted_social_domains", []))

    def validate_exam_update_sources(self, source_urls: list) -> bool:
        """
        Engine 1 Rule: Exam update facts MUST be backed by at least one official domain.
        """
        for url in source_urls:
            if self.is_official_domain(url):
                return True
        return False
