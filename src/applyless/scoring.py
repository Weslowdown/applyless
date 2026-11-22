from __future__ import annotations

import re
from dataclasses import dataclass

from .parser import JobPost, Requirement, evidence_lines, parse_jobs
from .redflags import detect_red_flags
from .taxonomy import related_categories, skill_by_name


@dataclass
class ScoredJob:
    job: JobPost
    score: int
    label: str
    matched: list[dict]
    missing_must: list[str]
    missing_preferred: list[str]
    coverage: float
    must_coverage: float
    confidence: str
    red_flags: list[dict]
    summary: str


def _title_alignment(title: str, resume_text: str) -> float:
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9.+#/-]{2,}", title)
        if token.lower() not in {"the", "and", "for", "with", "intern", "senior", "junior"}
    }
    if not tokens:
        return 0.35
    resume_lower = resume_text.lower()
    return sum(1 for token in tokens if token in resume_lower) / len(tokens)


def _unique_requirements(requirements: list[Requirement]) -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str, str]] = []
    for requirement in requirements:
        for skill in requirement.skills:
            key = (skill, requirement.priority)
            if key not in seen:
                seen.add(key)
                result.append((skill, requirement.priority, requirement.text))
    return result


def _score_job(
    post: JobPost,
    resume_text: str,
    evidence: dict[str, list[str]],
) -> ScoredJob:
    requirements = _unique_requirements(post.requirements)
    active = {
        "must": [(skill, text) for skill, priority, text in requirements if priority == "must"],
        "preferred": [(skill, text) for skill, priority, text in requirements if priority == "preferred"],
    }
    matched: list[dict] = []
    missing = {"must": [], "preferred": []}
    weighted_total = weighted_found = 0.0
    must_total = must_found = 0
    evidence_counts: list[int] = []

    for priority, weight in (("must", 2.0), ("preferred", 1.0)):
        for skill_name, requirement_text in active[priority]:
            if priority == "must":
                must_total += 1
            skill = skill_by_name(skill_name)
            aliases = evidence.get(skill_name, [])
            if aliases:
                weighted_found += weight
                if priority == "must":
                    must_found += 1
                evidence_counts.append(len(aliases))
                matched.append(
                    {
                        "skill": skill_name,
                        "category": skill.category if skill else "other",
                        "priority": priority,
                        "requirement": requirement_text,
                        "evidence": aliases[:2],
                        "evidence_count": len(aliases),
                    }
                )
            else:
                missing[priority].append(skill_name)
            weighted_total += weight

    coverage = weighted_found / weighted_total if weighted_total else 0.0
    must_coverage = must_found / must_total if must_total else coverage
    evidence_quality = (
        sum(min(count, 2) for count in evidence_counts) / (2 * len(evidence_counts))
        if evidence_counts
        else 0.0
    )
    alignment = _title_alignment(post.title, resume_text)
    raw_score = 100 * (0.68 * coverage + 0.20 * must_coverage + 0.07 * evidence_quality + 0.05 * alignment)
    score = max(0, min(99, round(raw_score)))

    if score >= 80 and not missing["must"]:
        label = "Strong fit"
    elif score >= 60:
        label = "Worth tailoring"
    elif score >= 45 or must_coverage >= 0.5:
        label = "Stretch"
    else:
        label = "Low match"

    recognized = len(requirements)
    confidence = "high" if recognized >= 6 else "medium" if recognized >= 3 else "low"
    flags = detect_red_flags(post.text, recognized)

    if not requirements:
        summary = "No recognized requirements were found. Add bullet points with concrete skills so the comparison can be useful."
    elif missing["must"]:
        summary = f"Your resume shows {must_found}/{must_total} must-have skills. Address {missing['must'][0]} before investing in a tailored application."
    elif matched:
        summary = f"Strong evidence in {len(matched)} recognized requirements, including {matched[0]['skill']}; the main opportunity is sharper, measurable proof."
    else:
        summary = "The requirements are recognizable, but the resume has no matching evidence yet."

    return ScoredJob(
        job=post,
        score=score,
        label=label,
        matched=sorted(matched, key=lambda item: item["priority"] != "must"),
        missing_must=sorted(set(missing["must"])),
        missing_preferred=sorted(set(missing["preferred"])),
        coverage=coverage,
        must_coverage=must_coverage,
        confidence=confidence,
        red_flags=[flag.to_dict() for flag in flags],
        summary=summary,
    )


def _to_dict(scored: ScoredJob, rank: int) -> dict:
    post = scored.job
    return {
        "rank": rank,
        "title": post.title,
        "company": post.company,
        "location": post.location,
        "salary": post.salary,
        "deadline": post.deadline or None,
        "score": scored.score,
        "label": scored.label,
        "summary": scored.summary,
        "confidence": scored.confidence,
        "coverage": round(scored.coverage * 100, 1),
        "must_coverage": round(scored.must_coverage * 100, 1),
        "requirement_count": len(_unique_requirements(post.requirements)),
        "matched": scored.matched,
        "missing_must": scored.missing_must,
        "missing_preferred": scored.missing_preferred,
        "red_flags": scored.red_flags,
        "next_actions": [
            f"Add a truthful, measurable example that proves {skill}." for skill in scored.missing_must[:3]
        ]
        + (
            ["Rewrite one strongest matched bullet as Scope → Action → Result. Do not invent metrics."]
            if scored.matched
            else ["Add a skills or projects section with tools you have genuinely used."]
        ),
    }


def score_batch(resume_text: str, jobs_text: str) -> dict:
    resume_text = (resume_text or "").strip()
    jobs_text = (jobs_text or "").strip()
    if len(resume_text) < 20:
        raise ValueError("Resume text is too short to evaluate.")
    if not jobs_text:
        raise ValueError("Add at least one job description.")

    posts = parse_jobs(jobs_text)
    if not posts:
        raise ValueError("No job descriptions were found.")
    evidence = evidence_lines(resume_text)
    scored = [_score_job(post, resume_text, evidence) for post in posts]
    scored.sort(key=lambda item: (item.score, len(item.matched)), reverse=True)
    return {
        "version": "0.1.0",
        "privacy": "Processed locally. Sent nowhere.",
        "jobs": [_to_dict(item, index + 1) for index, item in enumerate(scored)],
        "method": {
            "must_have_weight": 2,
            "preferred_weight": 1,
            "inputs": ["recognized skills", "resume evidence", "role-title alignment"],
            "not_used": ["gender", "age", "school prestige", "nationality"],
        },
    }

