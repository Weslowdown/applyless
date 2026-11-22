from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RedFlag:
    code: str
    label: str
    detail: str
    severity: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_RULES: tuple[tuple[str, str, str, str, str], ...] = (
    ("unpaid", r"\bunpaid\b|无薪|没有薪资", "Unpaid work", "The description explicitly mentions unpaid work.", "high"),
    ("commission", r"commission[- ]only|100%\s*commission|纯提成", "Commission-only pay", "Income may depend entirely on performance.", "high"),
    ("extreme_hours", r"\b24/7\b|on[- ]call 24|996|大小周|长期加班", "Extreme availability", "The role signals unusually broad or continuous availability expectations.", "medium"),
    ("vague_comp", r"\bcompetitive salary\b|薪资面议|待遇面议", "Compensation is vague", "Ask for a salary range before investing time in a long process.", "low"),
    ("many_hats", r"wear many hats|do everything|全能型|一人负责", "Very broad scope", "Clarify ownership boundaries and support before applying.", "medium"),
    ("urgent", r"\bimmediate start\b|急招|当天到岗|立刻到岗", "Urgent hiring language", "Urgency can signal churn or an undefined process; ask why the role is open.", "low"),
)


def detect_red_flags(text: str, requirement_count: int = 0) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for code, pattern, label, detail, severity in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(RedFlag(code, label, detail, severity))
    if requirement_count >= 14:
        flags.append(
            RedFlag(
                "over_specified",
                "Over-specified role",
                f"The description lists {requirement_count} recognized skill requirements. Check which are truly essential.",
                "medium",
            )
        )
    return flags

