from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from applyless.extract import ExtractionError, extract_resume_file
from applyless.parser import evidence_lines, parse_jobs, split_job_blocks
from applyless.redflags import detect_red_flags
from applyless.scoring import score_batch
from applyless.taxonomy import detect_skills


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resume = (ROOT / "samples/resume.txt").read_text(encoding="utf-8")
        self.jobs = (ROOT / "samples/jobs.txt").read_text(encoding="utf-8")

    def test_splits_three_jobs(self) -> None:
        self.assertEqual(len(split_job_blocks(self.jobs)), 3)

    def test_extracts_job_metadata_and_requirements(self) -> None:
        posts = parse_jobs(self.jobs)
        self.assertEqual(posts[0].title, "Machine Learning Intern")
        self.assertEqual(posts[0].company, "Northstar Labs")
        self.assertEqual(posts[0].location, "Shanghai / hybrid")
        self.assertGreaterEqual(len(posts[0].requirements), 5)

    def test_detects_chinese_skill_aliases(self) -> None:
        self.assertIn("Machine Learning", detect_skills("需要机器学习与数据可视化经验"))

    def test_resume_evidence_is_source_text(self) -> None:
        evidence = evidence_lines(self.resume)
        self.assertTrue(evidence["Python"])
        self.assertIn("Python", evidence["Python"][0])

    def test_source_syntax_supports_python_311(self) -> None:
        for path in (ROOT / "src").rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 11))


class ScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resume = (ROOT / "samples/resume.txt").read_text(encoding="utf-8")
        self.jobs = (ROOT / "samples/jobs.txt").read_text(encoding="utf-8")
        self.result = score_batch(self.resume, self.jobs)

    def test_returns_ranked_jobs(self) -> None:
        jobs = self.result["jobs"]
        self.assertEqual(len(jobs), 3)
        self.assertEqual([job["rank"] for job in jobs], [1, 2, 3])
        self.assertGreaterEqual(jobs[0]["score"], jobs[1]["score"])

    def test_strong_role_ranks_first(self) -> None:
        self.assertIn("Northstar", self.result["jobs"][0]["company"])
        self.assertEqual(self.result["jobs"][0]["label"], "Strong fit")

    def test_missing_must_haves_are_exposed(self) -> None:
        frontend = self.result["jobs"][-1]
        self.assertIn("TypeScript", frontend["missing_must"])
        self.assertIn("React", frontend["missing_must"])

    def test_next_actions_do_not_ask_for_invented_proof(self) -> None:
        for job in self.result["jobs"]:
            for action in job["next_actions"]:
                self.assertNotIn("fabricate", action.lower())
                self.assertNotIn("make up", action.lower())

    def test_short_resume_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            score_batch("too short", self.jobs)


class RedFlagTests(unittest.TestCase):
    def test_detects_scope_and_urgency_signals(self) -> None:
        flags = detect_red_flags("We wear many hats. Immediate start. Competitive salary.", 20)
        codes = {flag.code for flag in flags}
        self.assertIn("many_hats", codes)
        self.assertIn("urgent", codes)
        self.assertIn("over_specified", codes)


class ExtractionTests(unittest.TestCase):
    def test_plain_text_supports_utf8_and_gb18030(self) -> None:
        utf8 = "Python and SQL experience with product analytics".encode("utf-8")
        gb18030 = "数据分析和 Python 项目经验，负责报表和实验分析".encode("gb18030")
        self.assertIn("Python", extract_resume_file("resume.txt", utf8))
        self.assertIn("数据", extract_resume_file("简历.txt", gb18030))

    def test_docx_is_extracted_with_standard_library(self) -> None:
        from io import BytesIO
        from zipfile import ZipFile

        document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:r><w:t>Python</w:t></w:r><w:r><w:t> and SQL</w:t></w:r></w:p>
            <w:p><w:r><w:t>Built an A/B test for 8,000 users.</w:t></w:r></w:p>
          </w:body>
        </w:document>"""
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document)
        text = extract_resume_file("resume.docx", buffer.getvalue())
        self.assertEqual(text, "Python and SQL\nBuilt an A/B test for 8,000 users.")

    def test_unsupported_file_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ExtractionError, "Unsupported file type"):
            extract_resume_file("resume.pages", b"not a resume")


if __name__ == "__main__":
    unittest.main()

