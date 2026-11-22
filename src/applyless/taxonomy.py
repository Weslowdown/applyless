from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Iterable


class Skill:
    __slots__ = ("name", "category", "aliases")

    def __init__(self, name: str, category: str, aliases: Iterable[str]):
        self.name = name
        self.category = category
        self.aliases = tuple(sorted(set(aliases), key=len, reverse=True))

    def __repr__(self) -> str:
        return f"Skill({self.name!r}, {self.category!r})"


@lru_cache(maxsize=1)
def load_skills() -> tuple[Skill, ...]:
    path = files("applyless").joinpath("data/skills.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(Skill(item["name"], item["category"], item["aliases"]) for item in raw)


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if alias.isascii():
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


@lru_cache(maxsize=None)
def _compiled_aliases() -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    entries: list[tuple[str, str, re.Pattern[str]]] = []
    for skill in load_skills():
        for alias in skill.aliases:
            entries.append((skill.name, skill.category, _alias_pattern(alias)))
    return tuple(entries)


def detect_skills(text: str) -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    by_name = {skill.name: skill for skill in load_skills()}
    for name, _, pattern in _compiled_aliases():
        if pattern.search(text):
            found[name] = by_name[name]
    return found


def skill_by_name(name: str) -> Skill | None:
    return next((skill for skill in load_skills() if skill.name == name), None)


def related_categories(left: str, right: str) -> bool:
    return left == right and left not in {"soft", "language"}

