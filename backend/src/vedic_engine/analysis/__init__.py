"""Chart analysis built on a ``Kundli``: functional roles, planet strength, period judgement.

Every statement carries ``why`` (chart facts) and ``ref`` (classical source); texts and refs come
from ``analysis/data/*.json``. Traditional Jyotish interpretation: guidance, not certainty.
"""

from vedic_engine.analysis.dasha_judgement import (
    PeriodJudgement,
    Reason,
    judge_period,
    moon_waxing,
)
from vedic_engine.analysis.functional import FunctionalRole, Role, functional_roles
from vedic_engine.analysis.strength import ChartFacts, Factor, Strength, planet_strength

__all__ = [
    "ChartFacts",
    "Factor",
    "FunctionalRole",
    "PeriodJudgement",
    "Reason",
    "Role",
    "Strength",
    "functional_roles",
    "judge_period",
    "moon_waxing",
    "planet_strength",
]
