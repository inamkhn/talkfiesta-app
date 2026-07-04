import enum

class OAuthProvider(str, enum.Enum):
    GOOGLE = "GOOGLE"

class Goal(str, enum.Enum):
    FLUENCY = "FLUENCY"
    BUSINESS = "BUSINESS"
    EXAM = "EXAM"
    TRAVEL = "TRAVEL"

class SpeakingExerciseType(str, enum.Enum):
    CONVERSATIONAL = "CONVERSATIONAL"
    PUBLIC_SPEAKING = "PUBLIC_SPEAKING"
    IMPROMPTU = "IMPROMPTU"

class ContentSource(str, enum.Enum):
    AI = "AI"
    HUMAN = "HUMAN"

class ReviewStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"

class SubmissionStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class LiveSessionPersona(str, enum.Enum):
    FRIENDLY_TUTOR = "FRIENDLY_TUTOR"
    NATIVE_PEER = "NATIVE_PEER"
    EXAMINER = "EXAMINER"
    INTERVIEWER = "INTERVIEWER"

class LiveSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    TIMED_OUT = "TIMED_OUT"
    ERROR = "ERROR"

class VocabWordStatus(str, enum.Enum):
    LEARNING = "LEARNING"
    REVIEWING = "REVIEWING"
    MASTERED = "MASTERED"

class SuggestionSourceType(str, enum.Enum):
    SPEAKING = "SPEAKING"
    WRITING = "WRITING"

class SuggestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SHOWN = "SHOWN"
    ADDED_TO_QUEUE = "ADDED_TO_QUEUE"
    DISMISSED = "DISMISSED"

class WritingPromptType(str, enum.Enum):
    DESCRIPTIVE = "DESCRIPTIVE"
    NARRATIVE = "NARRATIVE"
    ARGUMENTATIVE = "ARGUMENTATIVE"

class InterviewDomain(str, enum.Enum):
    SOFTWARE_TECH = "SOFTWARE_TECH"
    BUSINESS_FINANCE = "BUSINESS_FINANCE"
    HEALTHCARE = "HEALTHCARE"
    SALES_MARKETING = "SALES_MARKETING"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    ACADEMIC_RESEARCH = "ACADEMIC_RESEARCH"
    GENERAL = "GENERAL"

class InterviewLevel(str, enum.Enum):
    ENTRY = "ENTRY"
    MID = "MID"
    SENIOR = "SENIOR"

class AgentType(str, enum.Enum):
    HR = "HR"
    TECHNICAL = "TECHNICAL"
    MANAGER = "MANAGER"

class WildcardCategory(str, enum.Enum):
    CLASSIC_CURVEBALL = "CLASSIC_CURVEBALL"
    BRAIN_TEASER = "BRAIN_TEASER"
    SELF_REFLECTION = "SELF_REFLECTION"
    PRESSURE_TEST = "PRESSURE_TEST"

class InterviewMode(str, enum.Enum):
    FULL_PANEL = "FULL_PANEL"
    SINGLE_AGENT = "SINGLE_AGENT"

class CompanyStyle(str, enum.Enum):
    STARTUP = "STARTUP"
    CORPORATE = "CORPORATE"

class PanelSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    ABANDONED = "ABANDONED"

class PanelEndReason(str, enum.Enum):
    NATURAL = "NATURAL"
    USER_TARGET_REACHED = "USER_TARGET_REACHED"
    HARD_CEILING_REACHED = "HARD_CEILING_REACHED"

class OverallVerdict(str, enum.Enum):
    STRONG_HIRE = "STRONG_HIRE"
    HIRE = "HIRE"
    MAYBE = "MAYBE"
    NO_HIRE = "NO_HIRE"

class PanelAgentFeedbackType(str, enum.Enum):
    HR = "HR"
    TECHNICAL = "TECHNICAL"
    MANAGER = "MANAGER"
    SUMMARY = "SUMMARY"

class AchievementModule(str, enum.Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"

class ContentGenerationModuleType(str, enum.Enum):
    SPEAKING = "SPEAKING"
    VOCABULARY = "VOCABULARY"
    WRITING = "WRITING"
    INTERVIEW_PANEL = "INTERVIEW_PANEL"

class ContentGenerationStatus(str, enum.Enum):
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    IN_REVIEW = "IN_REVIEW"
    PUBLISHED = "PUBLISHED"
