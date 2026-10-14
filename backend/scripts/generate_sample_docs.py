"""
Generate synthetic college policy PDF documents for development and testing.
Requires PyMuPDF (fitz) — installed as part of requirements.txt.

Usage (from backend/ directory):
    python scripts/generate_sample_docs.py

Output: sample_documents/ in the project root.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sample_documents",
)

DOCUMENTS = [
    {
        "filename": "student_handbook_2024_25.pdf",
        "title": "Student Handbook 2024-25",
        "pages": [
            (
                "STUDENT HANDBOOK — ACADEMIC YEAR 2024-25\n\nWelcome to Greenfield College of Technology.\n"
                "This handbook contains the regulations that govern student life, academic conduct, "
                "and administrative procedures."
            ),
            (
                "ATTENDANCE POLICY\n\n"
                "1. Minimum Attendance Requirement\n"
                "Students must maintain a minimum of 75% attendance in each subject per semester. "
                "Students falling below 65% attendance will not be permitted to sit the end-semester examination.\n\n"
                "2. Medical Leave\n"
                "Students absent due to medical reasons must submit a medical certificate signed by a "
                "registered medical practitioner within three working days of returning to college. "
                "Approved medical leave is counted as attended for the purpose of the 75% requirement, "
                "up to a maximum of 10 days per semester.\n\n"
                "3. Condonation\n"
                "The Principal may condone attendance deficiency between 65% and 74% in exceptional "
                "circumstances on the recommendation of the class advisor and payment of a condonation fee "
                "of ₹500."
            ),
            (
                "EXAMINATION REGULATIONS\n\n"
                "1. End-Semester Examinations\n"
                "End-semester examinations are held in November–December (odd semester) and April–May "
                "(even semester). The examination schedule is published at least 30 days in advance.\n\n"
                "2. Internal Assessment\n"
                "Internal marks (40% of total) are based on: two cycle tests (15 marks each), "
                "one model examination (20 marks), and assignment/seminar (10 marks). "
                "The best two out of three cycle tests are counted.\n\n"
                "3. Eligibility\n"
                "A student must have a minimum of 75% attendance and have paid all dues to be eligible "
                "to appear in the end-semester examination. No supplemental examination is conducted for "
                "first-year students."
            ),
            (
                "REVALUATION AND RETOTALLING\n\n"
                "Students who wish to challenge their end-semester examination marks may apply for:\n\n"
                "• Retotalling: Re-checking the addition of marks. Fee: ₹200 per paper. "
                "Applications must be submitted within 15 days of result publication.\n\n"
                "• Revaluation: Re-evaluation of answer scripts by an independent examiner. "
                "Fee: ₹500 per paper. Applications must be submitted within 30 days of result publication.\n\n"
                "Results of revaluation are final and binding. Marks obtained after revaluation, "
                "whether higher or lower, will be treated as the official marks."
            ),
            (
                "STUDENT CONDUCT\n\n"
                "1. Code of Conduct\n"
                "Students are expected to behave with dignity and respect towards faculty, staff, "
                "and fellow students at all times on and off campus.\n\n"
                "2. Mobile Phones\n"
                "Mobile phones are strictly prohibited inside examination halls. Use of mobile phones "
                "in classrooms during instruction hours is not permitted. Violation may result in "
                "confiscation and disciplinary action.\n\n"
                "3. Ragging\n"
                "Ragging in any form is a criminal offence under the relevant University Grants Commission "
                "regulations. Any student found guilty of ragging will be expelled from the institution. "
                "Students experiencing ragging should report immediately to the Anti-Ragging Committee."
            ),
        ],
    },
    {
        "filename": "fee_regulations_2024_25.pdf",
        "title": "Fee Regulations and Scholarship Policy 2024-25",
        "pages": [
            (
                "FEE REGULATIONS — ACADEMIC YEAR 2024-25\n\n"
                "All fee-related matters are governed by the regulations set forth in this document. "
                "Students are advised to retain receipts for all payments made to the college."
            ),
            (
                "TUITION AND SPECIAL FEES\n\n"
                "Annual tuition fee: ₹85,000 (B.E./B.Tech programs)\n"
                "Examination fee: ₹1,200 per semester (covers all subjects in the registered semester)\n"
                "Library fee: ₹1,500 per year\n"
                "Laboratory fee: ₹3,000 per year (engineering programs)\n"
                "Sports and cultural fee: ₹500 per year\n\n"
                "All fees are due by the dates specified in the academic calendar. "
                "A late fee of ₹50 per day is levied on overdue payments up to a maximum of ₹1,000."
            ),
            (
                "SCHOLARSHIP SCHEMES\n\n"
                "1. Merit Scholarship\n"
                "Students securing the top 5% marks in the university examination within their department "
                "are awarded a merit scholarship of ₹10,000 per semester. "
                "The scholarship is credited directly to the student's bank account.\n\n"
                "2. Government Scholarships\n"
                "Students belonging to SC/ST/OBC categories may apply for government scholarships "
                "through the National Scholarship Portal (scholarships.gov.in). "
                "The college fee concession committee processes applications every August.\n\n"
                "3. Sports Quota Fee Concession\n"
                "Students admitted under the sports quota receive a 50% concession on tuition fees "
                "subject to continued participation and maintaining good academic standing."
            ),
            (
                "FEE REFUND POLICY\n\n"
                "Refunds on withdrawal from the programme are processed as follows:\n\n"
                "• Before the commencement of the academic year: 100% refund (minus ₹1,000 processing fee)\n"
                "• Within 15 days of commencement: 80% refund\n"
                "• 16–30 days after commencement: 50% refund\n"
                "• After 30 days: No refund\n\n"
                "Examination fees are non-refundable once the examination schedule is published. "
                "Refund requests must be submitted in writing to the Finance Office."
            ),
        ],
    },
    {
        "filename": "academic_calendar_2024_25.pdf",
        "title": "Academic Calendar 2024-25",
        "pages": [
            (
                "ACADEMIC CALENDAR — 2024-25\n\n"
                "This calendar sets out the key academic dates for both semesters of the academic year 2024-25. "
                "Dates are subject to revision; students should check the college notice board and website "
                "for updates."
            ),
            (
                "ODD SEMESTER (JULY – NOVEMBER 2024)\n\n"
                "01 Jul 2024 — Commencement of odd semester\n"
                "15 Jul 2024 — Last date for fee payment without late fee\n"
                "02 Sep 2024 — First cycle test (weeks 9–10)\n"
                "14 Oct 2024 — Second cycle test (weeks 15–16)\n"
                "28 Oct 2024 — Last working day of odd semester\n"
                "04 Nov 2024 — Model examination begins\n"
                "18 Nov 2024 — End-semester examination begins\n"
                "28 Nov 2024 — End-semester examination ends\n"
                "15 Dec 2024 — Publication of end-semester results"
            ),
            (
                "EVEN SEMESTER (JANUARY – MAY 2025)\n\n"
                "02 Jan 2025 — Commencement of even semester\n"
                "17 Jan 2025 — Last date for fee payment without late fee\n"
                "03 Mar 2025 — First cycle test (weeks 9–10)\n"
                "14 Apr 2025 — Second cycle test (weeks 15–16)\n"
                "28 Apr 2025 — Last working day of even semester\n"
                "05 May 2025 — Model examination begins\n"
                "19 May 2025 — End-semester examination begins\n"
                "29 May 2025 — End-semester examination ends\n"
                "20 Jun 2025 — Publication of even semester results"
            ),
            (
                "HOLIDAYS AND VACATION\n\n"
                "Summer vacation: 02 Jun 2025 – 28 Jun 2025\n"
                "Deepavali holidays: 31 Oct – 02 Nov 2024\n"
                "Christmas and New Year: 25 Dec 2024 – 01 Jan 2025\n"
                "Pongal holidays: 13 Jan – 16 Jan 2025\n\n"
                "Note: The college observes all gazetted state holidays as notified by the "
                "Tamil Nadu government. Additional holidays may be declared by the Principal."
            ),
        ],
    },
]


def generate() -> None:
    try:
        import fitz
    except ImportError:
        print("PyMuPDF is required: pip install PyMuPDF")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for doc_spec in DOCUMENTS:
        path = os.path.join(OUTPUT_DIR, doc_spec["filename"])
        doc = fitz.open()

        for page_text in doc_spec["pages"]:
            page = doc.new_page(width=595, height=842)  # A4
            # Insert text with a simple layout
            rect = fitz.Rect(50, 60, 545, 800)
            page.insert_textbox(
                rect,
                page_text,
                fontsize=11,
                fontname="helv",
                color=(0, 0, 0),
                align=0,
            )

        doc.save(path)
        doc.close()
        print(f"Generated: {path} ({len(doc_spec['pages'])} pages)")

    print(f"\nDone. {len(DOCUMENTS)} sample documents written to {OUTPUT_DIR}")
    print("Upload them via the admin dashboard to start testing RAG queries.")


if __name__ == "__main__":
    generate()
