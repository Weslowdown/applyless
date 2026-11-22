from __future__ import annotations

import re
from dataclasses import dataclass, field

from .taxonomy import detect_skills


_JOB_BREAK = re.compile(
    r"^\s*(?:#{2,3}\s+(?P<md>.+?)\s*$|(?:={2,}|-{3,})\s*(?:JOB\s*:\s*)?(?P<rule>.+?)\s*(?:={2,}|-{3,})?\s*$)",
    re.IGNORECASE,
)
_FIELD = re.compile(
    r"^\s*(?P<key>company|role|title|position|location|salary|deadline|company name|job title)\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-*+•·▪◦]|\d+[.)、])\s*(?P<text>.+?)\s*$")
_SECTION = re.compile(
    r"^\s*(?P<title>requirements?|qualifications?|what you(?:'|’)ll need|must haves?|preferred|nice to haves?|bonus|about (?:the )?role|responsibilities|what you(?:'|’)ll do|岗位要求|任职要求|必备条件|加分项|优先条件|优先|工作职责|职位描述)\s*:?\s*$",
    re.IGNORECASE,
)
_MUST_HEADINGS = re.compile(
    r"requirements?|qualifications?|what you(?:'|’)ll need|must haves?|岗位要求|任职要求|必备条件",
    re.IGNORECASE,
)
_PREFERRED_HEADINGS = re.compile(
    r"preferred|nice to haves?|bonus|加分项|优先条件|优先",
    re.IGNORECASE,
)
_PREFERRED_LANGUAGE = re.compile(
    r"\b(?:preferred|nice to have|bonus|plus|advantage(?:ous)?)\b|加分|优先|更佳|最好",
    re.IGNORECASE,
)
_NUMBERED_LINE = re.compile(r"^\s*\d+[.)、]\s+.+$")


@dataclass
class Requirement:
    text: str
    priority: str
    skills: list[str] = field(default_factory=list)


@dataclass
class JobPost:
    title: str
    company: str
    location: str
    salary: str
    deadline: str
    text: str
    requirements: list[Requirement]


def _clean_heading(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip(" =-|")).strip()


def _looks_like_header(line: str) -> re.Match[str] | None:
    match = _JOB_BREAK.match(line)
    if not match:
        return None
    label = (match.group("md") or match.group("rule") or "").strip()
    if not label:
        return None
    if re.fullmatch(r"[-=*_\s]+", label):
        return None
    return match


def split_job_blocks(text: str) -> list[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    starts = [index for index, line in enumerate(lines) if _looks_like_header(line)]
    if not starts:
        stripped = text.strip()
        return [stripped] if stripped else []
    if starts[0] != 0:
        prefix = "\n".join(lines[: starts[0]]).strip()
        starts = ([0] if prefix else []) + starts
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if block:
            blocks.append(block)
    return blocks


def _header_fields(line: str) -> tuple[str, str]:
    header = _looks_like_header(line)
    if not header:
        return "", ""
    label = _clean_heading(header.group("md") or header.group("rule") or "")
    pieces = [part.strip() for part in re.split(r"\s*(?:\||—|–|@)\s*", label) if part.strip()]
    if len(pieces) >= 2:
        return pieces[0], pieces[1]
    if len(pieces) == 1 and label.lower() not in {"job", "role", "职位", "岗位"}:
        return pieces[0], ""
    return "", ""


def _requirement_chunks(lines: list[str]) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    priority = "must"
    in_requirements = False
    for line in lines:
        section = _SECTION.match(line)
        if section:
            title = section.group("title")
            if _PREFERRED_HEADINGS.search(title):
                priority = "preferred"
                in_requirements = True
            elif _MUST_HEADINGS.search(title):
                priority = "must"
                in_requirements = True
            else:
                in_requirements = False
            continue

        bullet = _BULLET.match(line)
        candidate = bullet.group("text") if bullet else line.strip()
        if not candidate or _FIELD.match(line):
            continue
        if not detect_skills(candidate):
            continue
        if in_requirements or bullet or _NUMBERED_LINE.match(line):
            item_priority = "preferred" if _PREFERRED_LANGUAGE.search(candidate) else priority
            for sentence in re.split(r"(?<=[.!?。！？])\s+", candidate):
                if detect_skills(sentence):
                    chunks.append((sentence.strip(), item_priority))
    return chunks


def parse_job(block: str) -> JobPost:
    lines = [line.rstrip() for line in block.splitlines()]
    title, company = "", ""
    if lines:
        title, company = _header_fields(lines[0])

    fields: dict[str, str] = {}
    for line in lines:
        field_match = _FIELD.match(line)
        if field_match:
            key = field_match.group("key").lower()
            value = field_match.group("value").strip()
            if key in {"role", "title", "position", "job title"}:
                title = value
            elif key in {"company", "company name"}:
                company = value
            else:
                fields[key] = value

    title = title or fields.get("role") or "Untitled role"
    company = company or fields.get("company") or "Unknown company"
    location = fields.get("location", "Location not listed")
    salary = fields.get("salary", "Salary not listed")
    deadline = fields.get("deadline", "")

    requirements: list[Requirement] = []
    seen: set[tuple[str, str]] = set()
    for chunk, priority in _requirement_chunks(lines):
        skills = sorted(detect_skills(chunk))
        if not skills:
            continue
        key = (chunk.lower(), priority)
        if key in seen:
            continue
        seen.add(key)
        requirements.append(Requirement(chunk, priority, skills))

    return JobPost(
        title=title.strip(),
        company=company.strip(),
        location=location.strip(),
        salary=salary.strip(),
        deadline=deadline.strip(),
        text=block.strip(),
        requirements=requirements,
    )


def parse_jobs(text: str) -> list[JobPost]:
    return [parse_job(block) for block in split_job_blocks(text)]


def evidence_lines(resume_text: str) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    lines = [line.strip(" \t-*•·") for line in resume_text.splitlines() if line.strip()]
    for line in lines:
        for skill in detect_skills(line):
            bucket = evidence.setdefault(skill, [])
            if line not in bucket and len(bucket) < 3:
                bucket.append(line[:320])
    return evidence

