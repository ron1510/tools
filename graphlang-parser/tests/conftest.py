from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile(
    "default",
    max_examples=50,
    deadline=200,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "extended",
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("OPIUM_HYPOTHESIS_PROFILE", "default"))
