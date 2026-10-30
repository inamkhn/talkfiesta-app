"""Import every mapped class so ``Base.metadata`` is complete (V4 schema).

Alembic and any tooling that needs the full schema must import this module.
Nothing should import it in application request paths.
"""

from __future__ import annotations

from app.modules.assessment import models as assessment_models
from app.modules.auth import models as auth_models
from app.modules.content import models as content_models
from app.modules.gamification import models as gamification_models
from app.modules.jobs import models as jobs_models
from app.modules.learning import models as learning_models
from app.modules.media import models as media_models
from app.modules.practice import models as practice_models
from app.modules.vocabulary import models as vocabulary_models

__all__ = [
    "assessment_models",
    "auth_models",
    "content_models",
    "gamification_models",
    "jobs_models",
    "learning_models",
    "media_models",
    "practice_models",
    "vocabulary_models",
]
