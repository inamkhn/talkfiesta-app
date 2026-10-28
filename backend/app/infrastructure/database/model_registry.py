"""Import every mapped class so ``Base.metadata`` is complete.

Alembic and any tooling that needs the full schema must import this module.
Nothing should import it in application request paths.
"""

from __future__ import annotations

from app.modules.assessment import models as assessment_models
from app.modules.auth import models as auth_models
from app.modules.curriculum import models as curriculum_models
from app.modules.jobs import models as jobs_models
from app.modules.learning_plans import models as learning_plans_models
from app.modules.media import models as media_models
from app.modules.onboarding import models as onboarding_models

__all__ = [
    "assessment_models",
    "auth_models",
    "curriculum_models",
    "jobs_models",
    "learning_plans_models",
    "media_models",
    "onboarding_models",
]
