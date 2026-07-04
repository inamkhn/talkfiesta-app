from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import all models here so that Alembic can discover them through Base.metadata
from app.db.models.user import User, UserLearningProfile
from app.db.models.speaking import SpeakingExercise, SpeakingSubmission, LiveConversationSession
from app.db.models.vocabulary import (
    VocabularyWord,
    VocabularyExerciseBank,
    UserVocabulary,
    VocabularyPracticeSession,
    PersonalizedVocabSuggestion,
)
from app.db.models.writing import WritingPrompt, WritingSubmission, WritingSubmissionVersion
from app.db.models.interview import (
    DomainQuestionBank,
    WildcardQuestionBank,
    InterviewPanelSession,
    PanelRound,
    PanelResponse,
    PanelAgentFeedback,
)
from app.db.models.progress import DailyProgress, Achievement, UserAchievement
from app.db.models.content_generation import ContentGenerationBatch
