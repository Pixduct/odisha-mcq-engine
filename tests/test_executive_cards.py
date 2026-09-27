import os
import sys
import time
from PIL import Image

sys.path.insert(0, r"c:\Users\Naresh Samal\Downloads\OdishaExamPrep Website\automations")
from shared.imagen_generator import generate_blog_imagen_banner

def test_cards():
    cases = [
        {
            "title": "Odisha High Court Typist DEO Result 2026 Out: Download Merit List PDF",
            "org": "High Court of Orissa",
            "category": "Results & Merit List",
            "context": "The High Court of Orissa has officially published the Junior Grade Typist and Data Entry Operator result. Shortlisted candidates must report for document verification.",
            "slug": "test-high-court-typist-result"
        },
        {
            "title": "OPSC Odisha Civil Services OAS 2026 Notification PDF: 399 Vacancies Apply Online",
            "org": "Odisha Public Service Commission",
            "category": "Official Recruitment",
            "context": "Odisha Public Service Commission invites online applications for OCS 2026 examination for Group A and Group B executive cadres.",
            "slug": "test-opsc-ocs-2026"
        },
        {
            "title": "OSSSC Combined Recruitment Exam 2026: RI, ICDS Supervisor, Amin Exam Date Announced",
            "org": "Odisha Subordinate Staff Selection Commission",
            "category": "Exam Date Announced",
            "context": "OSSSC has officially notified the preliminary examination dates for Revenue Inspector, ARI, and Amin positions across all districts.",
            "slug": "test-osssc-cre-dates"
        },
        {
            "title": "Odisha Police Constable Recruitment 2026: 1422 Vacancies Notification PDF",
            "org": "State Police Recruitment Board, Odisha",
            "category": "Official Recruitment",
            "context": "State Police Recruitment Board announces Constable civil vacancies in various battalions and districts. Physical standard tests details included.",
            "slug": "test-odisha-police-constable"
        },
        {
            "title": "Daily Odisha Current Affairs & National GK Digest: 27 September 2026",
            "org": "Odisha State Strategy & Editorial",
            "category": "Daily Current Affairs",
            "context": "Comprehensive daily current affairs roundup covering Odisha government schemes, national milestones, awards, appointments, and high-yield MCQs.",
            "slug": "test-daily-current-affairs-sep-27"
        }
    ]

    print("=====================================================")
    print("  EXECUTIVE GRAPHIC CARD TEST SUITE")
    print("=====================================================")

    for i, tc in enumerate(cases, 1):
        t0 = time.time()
        res = generate_blog_imagen_banner(
            title=tc["title"],
            organization=tc["org"],
            category=tc["category"],
            context_summary=tc["context"],
            slug=tc["slug"]
        )
        elapsed = time.time() - t0

        local_path = res.get("local_path")
        assert local_path and os.path.exists(local_path), f"File missing: {local_path}"

        img = Image.open(local_path)
        assert img.size == (1200, 675), f"Bad dimensions: {img.size}"

        print(f"[{i}/5] PASS: {tc['org']} ({elapsed:.2f}s)")
        print(f"      File: {os.path.basename(local_path)} | Size: {os.path.getsize(local_path)} bytes")
        print(f"      URL:  {res.get('image_url')}")
        print("-----------------------------------------------------")

    print("ALL 5 EXECUTIVE CARD TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_cards()
