"""Deterministic, idempotent seeders for placement assessment bank and 21-day curricula."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.assessment.blueprint import LEVELS
from app.modules.content.models import ContentItem

CURRICULUM_RELEASE = "curriculum-v1"

GRAMMAR_QUESTIONS: dict[str, list[tuple[str, list[tuple[str, str]], str]]] = {
    "A1": [
        (
            "Choose the correct form to complete the sentence: 'She ___ to work every morning.'",
            [("a", "walk"), ("b", "walks"), ("c", "walking"), ("d", "walked")],
            "b",
        ),
        (
            "Select the word that fits best: 'There ___ two books on the desk.'",
            [("a", "is"), ("b", "am"), ("c", "are"), ("d", "be")],
            "c",
        ),
        (
            "Complete the question: '___ you like coffee or tea?'",
            [("a", "Does"), ("b", "Do"), ("c", "Are"), ("d", "Is")],
            "b",
        ),
        (
            "Choose the right pronoun: 'My brother is a teacher. ___ works at a high school.'",
            [("a", "Him"), ("b", "His"), ("c", "He"), ("d", "Her")],
            "c",
        ),
    ],
    "A2": [
        (
            "Complete the sentence: 'I ___ watching a movie when you called me last night.'",
            [("a", "was"), ("b", "were"), ("c", "am"), ("d", "have")],
            "a",
        ),
        (
            "Choose the correct comparative form: 'This train is ___ than the bus.'",
            [("a", "fast"), ("b", "more fast"), ("c", "faster"), ("d", "fastest")],
            "c",
        ),
        (
            "Select the best option: 'Have you ___ visited London?'",
            [("a", "ever"), ("b", "yet"), ("c", "already"), ("d", "since")],
            "a",
        ),
        (
            "Complete the sentence: 'We don't have ___ milk left in the fridge.'",
            [("a", "many"), ("b", "some"), ("c", "any"), ("d", "a")],
            "c",
        ),
    ],
    "B1": [
        (
            "Choose the correct form: 'If I ___ more free time, I would learn another language.'",
            [("a", "have"), ("b", "had"), ("c", "will have"), ("d", "would have")],
            "b",
        ),
        (
            "Complete the sentence: 'She has been working at this company ___ five years.'",
            [("a", "since"), ("b", "from"), ("c", "during"), ("d", "for")],
            "d",
        ),
        (
            "Select the right passive form: 'The new bridge ___ last year.'",
            [("a", "built"), ("b", "was built"), ("c", "is building"), ("d", "has built")],
            "b",
        ),
        (
            "Choose the best connector: '___ the heavy rain, the outdoor concert continued.'",
            [("a", "Although"), ("b", "Because"), ("c", "Despite"), ("d", "However")],
            "c",
        ),
    ],
    "B2": [
        (
            "Complete the sentence: 'By the time the guests arrived, we ___ preparing dinner.'",
            [
                ("a", "have finished"),
                ("b", "had finished"),
                ("c", "finished"),
                ("d", "were finishing"),
            ],
            "b",
        ),
        (
            "Choose the correct structure: 'I wish I ___ harder for the exam last week.'",
            [("a", "studied"), ("b", "would study"), ("c", "had studied"), ("d", "have studied")],
            "c",
        ),
        (
            "Select the best option: 'The manager suggested that the report ___ before Friday.'",
            [
                ("a", "be submitted"),
                ("b", "is submitting"),
                ("c", "will submit"),
                ("d", "submitted"),
            ],
            "a",
        ),
        (
            "Complete the sentence: 'Hardly ___ the office when the phone started ringing.'",
            [
                ("a", "I had entered"),
                ("b", "had I entered"),
                ("c", "I entered"),
                ("d", "did I entered"),
            ],
            "b",
        ),
    ],
    "C1": [
        (
            "Choose the best form: 'Not only ___ the deadline, but the team also exceeded quality targets.'",
            [
                ("a", "they met"),
                ("b", "did they meet"),
                ("c", "they did meet"),
                ("d", "met they"),
            ],
            "b",
        ),
        (
            "Complete the conditional: '___ you require any further assistance, please contact our team.'",
            [("a", "Should"), ("b", "Were"), ("c", "Had"), ("d", "Unless")],
            "a",
        ),
        (
            "Select the correct option: 'The proposal, ___ implications are still being debated, was deferred.'",
            [("a", "which"), ("b", "whom"), ("c", "whose"), ("d", "that")],
            "c",
        ),
        (
            "Complete the sentence: 'Had it not been for her timely intervention, the project ___.'",
            [
                ("a", "would collapse"),
                ("b", "would have collapsed"),
                ("c", "will collapse"),
                ("d", "collapsed"),
            ],
            "b",
        ),
    ],
    "C2": [
        (
            "Choose the most precise structure: 'So intricate ___ that even veteran analysts struggled to model it.'",
            [
                ("a", "the mechanism was"),
                ("b", "was the mechanism"),
                ("c", "were the mechanism"),
                ("d", "has the mechanism"),
            ],
            "b",
        ),
        (
            "Complete the sentence: 'Be that as it ___, we must still honor the original agreement.'",
            [("a", "can"), ("b", "may"), ("c", "will"), ("d", "would")],
            "b",
        ),
        (
            "Select the correct form: 'Little ___ that the seemingly minor adjustment would transform the system.'",
            [
                ("a", "they suspected"),
                ("b", "did they suspect"),
                ("c", "they had suspected"),
                ("d", "suspected they"),
            ],
            "b",
        ),
        (
            "Complete the clause: 'Whatever the panel's objections ___, the empirical findings remain robust.'",
            [("a", "might be"), ("b", "would have"), ("c", "could been"), ("d", "shall")],
            "a",
        ),
    ],
}

VOCABULARY_QUESTIONS: dict[str, list[tuple[str, list[tuple[str, str]], str]]] = {
    "A1": [
        (
            "Which word means 'the meal you eat in the morning'?",
            [("a", "Dinner"), ("b", "Breakfast"), ("c", "Snack"), ("d", "Supper")],
            "b",
        ),
        (
            "Choose the opposite of 'expensive':",
            [("a", "Cheap"), ("b", "Heavy"), ("c", "Large"), ("d", "Quick")],
            "a",
        ),
        (
            "Complete the sentence: 'Please ___ the door when you leave.'",
            [("a", "close"), ("b", "wear"), ("c", "cook"), ("d", "listen")],
            "a",
        ),
        (
            "Where do you go to borrow books?",
            [("a", "Bakery"), ("b", "Library"), ("c", "Airport"), ("d", "Pharmacy")],
            "b",
        ),
    ],
    "A2": [
        (
            "Choose the best word: 'Our flight was ___ by two hours because of fog.'",
            [("a", "delayed"), ("b", "repaired"), ("c", "borrowed"), ("d", "invited")],
            "a",
        ),
        (
            "Which word describes someone who enjoys meeting and talking to people?",
            [("a", "Outgoing"), ("b", "Careless"), ("c", "Nervous"), ("d", "Silent")],
            "a",
        ),
        (
            "Complete the sentence: 'Can you ___ me a favor and send this email?'",
            [("a", "make"), ("b", "do"), ("c", "take"), ("d", "give")],
            "b",
        ),
        (
            "Select the best fit: 'She bought a return ___ for the train to Manchester.'",
            [("a", "receipt"), ("b", "ticket"), ("c", "menu"), ("d", "bill")],
            "b",
        ),
    ],
    "B1": [
        (
            "Choose the word that fits best: 'Regular exercise is ___ for both physical and mental health.'",
            [("a", "beneficial"), ("b", "artificial"), ("c", "temporary"), ("d", "reluctant")],
            "a",
        ),
        (
            "Complete the sentence: 'We need to find a ___ solution before the problem gets worse.'",
            [("a", "practical"), ("b", "frequent"), ("c", "curious"), ("d", "distant")],
            "a",
        ),
        (
            "Which word means 'to Persuade someone to do something'?",
            [("a", "Convince"), ("b", "Prevent"), ("c", "Remind"), ("d", "Avoid")],
            "a",
        ),
        (
            "Complete the sentence: 'He was ___ to team leader after two years of strong performance.'",
            [("a", "promoted"), ("b", "resigned"), ("c", "expanded"), ("d", "retired")],
            "a",
        ),
    ],
    "B2": [
        (
            "Choose the best word: 'The company implemented stricter policies to ___ data privacy.'",
            [("a", "safeguard"), ("b", "overlook"), ("c", "undermine"), ("d", "provoke")],
            "a",
        ),
        (
            "Complete the sentence: 'There has been a ___ shift toward remote collaboration in recent years.'",
            [("a", "substantial"), ("b", "superficial"), ("c", "negligible"), ("d", "fragile")],
            "a",
        ),
        (
            "Which word is closest in meaning to 'inevitable'?",
            [("a", "Unavoidable"), ("b", "Unlikely"), ("c", "Optional"), ("d", "Debatable")],
            "a",
        ),
        (
            "Complete the sentence: 'Her explanation was so ___ that everyone immediately understood the plan.'",
            [("a", "coherent"), ("b", "ambiguous"), ("c", "obscure"), ("d", "tentative")],
            "a",
        ),
    ],
    "C1": [
        (
            "Choose the most accurate word: 'The auditor identified several ___ between the two financial reports.'",
            [
                ("a", "discrepancies"),
                ("b", "redundancies"),
                ("c", "conventions"),
                ("d", "endorsements"),
            ],
            "a",
        ),
        (
            "Complete the sentence: 'The keynote speaker offered a ___ analysis of global supply chains.'",
            [("a", "compelling"), ("b", "complacent"), ("c", "cursory"), ("d", "Derivative")],
            "a",
        ),
        (
            "Which word means 'to lessen the severity of an undesirable outcome'?",
            [("a", "Mitigate"), ("b", "Exacerbate"), ("c", "Proliferate"), ("d", "Substantiate")],
            "a",
        ),
        (
            "Complete the sentence: 'The team reached a ___ compromise after weeks of negotiation.'",
            [("a", "pragmatic"), ("b", "perfunctory"), ("c", "sporadic"), ("d", "volatile")],
            "a",
        ),
    ],
    "C2": [
        (
            "Choose the word that best fits: 'His seemingly ___ remarks actually concealed a carefully prepared argument.'",
            [
                ("a", "offhand"),
                ("b", "unequivocal"),
                ("c", "methodical"),
                ("d", "ostentatious"),
            ],
            "a",
        ),
        (
            "Complete the sentence: 'The treatise is notable for its ___ synthesis of historical and economic data.'",
            [("a", "erudite"), ("b", "pedestrian"), ("c", "ephemeral"), ("d", "capricious")],
            "a",
        ),
        (
            "Which word is closest in meaning to 'ephemeral'?",
            [("a", "Short-lived"), ("b", "Perpetual"), ("c", "Ubiquitous"), ("d", "Intractable")],
            "a",
        ),
        (
            "Complete the sentence: 'The committee rejected the proposal as ___ and lacking empirical grounding.'",
            [("a", "specious"), ("b", "fastidious"), ("c", "salient"), ("d", "assiduous")],
            "a",
        ),
    ],
}


def build_assessment_bank_items(
    release_key: str | None = None,
) -> list[ContentItem]:
    """Build deterministic placement-bank-v1 ContentItem rows."""
    release = release_key or settings.assessment_content_release
    items: list[ContentItem] = []

    for skill, bank in (
        ("GRAMMAR", GRAMMAR_QUESTIONS),
        ("VOCABULARY", VOCABULARY_QUESTIONS),
    ):
        for level in LEVELS:
            for idx, (prompt, choices, correct_id) in enumerate(bank[level], start=1):
                item_id = uuid5(
                    NAMESPACE_URL,
                    f"talkfiesta:{release}:assessment:{skill}:{level}:{idx}",
                )
                items.append(
                    ContentItem(
                        id=item_id,
                        release_key=release,
                        kind="ASSESSMENT_QUESTION",
                        status="PUBLISHED",
                        cefr_level=level,
                        title=f"{skill.title()} Check ({level} #{idx})",
                        body={
                            "kind": "MULTIPLE_CHOICE",
                            "skill": skill,
                            "prompt": prompt,
                            "choices": [
                                {"id": cid, "text": text} for cid, text in choices
                            ],
                            "correct_choice_id": correct_id,
                        },
                        content_version=1,
                    )
                )

    writing_id = uuid5(NAMESPACE_URL, f"talkfiesta:{release}:assessment:WRITING:1")
    items.append(
        ContentItem(
            id=writing_id,
            release_key=release,
            kind="ASSESSMENT_QUESTION",
            status="PUBLISHED",
            cefr_level="B1",
            title="Short Writing Placement Prompt",
            body={
                "kind": "SHORT_WRITING",
                "skill": "WRITING",
                "prompt": (
                    "Write a short response (40–120 words) about a skill or project you "
                    "recently worked on, why it mattered to you, and what you would like "
                    "to improve next."
                ),
                "min_words": 20,
                "max_words": 250,
                "rubric": {
                    "version": "placement-v1",
                    "criteria": [
                        "grammar",
                        "vocabulary",
                        "coherence",
                        "task_completion",
                    ],
                },
            },
            content_version=1,
        )
    )

    speaking_id = uuid5(NAMESPACE_URL, f"talkfiesta:{release}:assessment:SPEAKING:1")
    items.append(
        ContentItem(
            id=speaking_id,
            release_key=release,
            kind="ASSESSMENT_QUESTION",
            status="PUBLISHED",
            cefr_level="B1",
            title="Spoken Placement Prompt",
            body={
                "kind": "RECORDED_SPEAKING",
                "skill": "SPEAKING",
                "prompt": (
                    "Introduce yourself briefly and describe how you use English in your "
                    "daily life or work, and what situations you want to feel more confident in."
                ),
                "suggested_seconds": 45,
                "max_seconds": 120,
                "rubric": {
                    "version": "placement-v1",
                    "criteria": [
                        "grammar",
                        "vocabulary",
                        "coherence",
                        "task_completion",
                    ],
                },
            },
            content_version=1,
        )
    )
    return items


BASE_VOCAB_WORDS: list[tuple[str, str, str, str, str, list[str], list[str]]] = [
    (
        "collaborate",
        "verb",
        "To work jointly with others on an activity or project.",
        "/kəˈlæb.ə.reɪt/",
        "Our engineering and design teams collaborate closely every sprint.",
        ["cooperate", "partner"],
        ["compete"],
    ),
    (
        "resilient",
        "adjective",
        "Able to recover quickly from difficult conditions or setbacks.",
        "/rɪˈzɪl.jənt/",
        "A resilient mindset helps learners stay consistent over time.",
        ["adaptable", "strong"],
        ["fragile"],
    ),
    (
        "articulate",
        "adjective",
        "Having or showing the ability to speak fluently and coherently.",
        "/ɑːrˈtɪk.jə.lət/",
        "She gave an articulate summary of the quarterly roadmap.",
        ["eloquent", "clear"],
        ["inarticulate"],
    ),
    (
        "prioritize",
        "verb",
        "To designate or treat something as more important than other things.",
        "/praɪˈɔːr.ə.taɪz/",
        "Let's prioritize the customer-facing fixes before refactoring.",
        ["rank", "focus"],
        ["neglect"],
    ),
    (
        "perspective",
        "noun",
        "A particular attitude toward or way of regarding something; a point of view.",
        "/pərˈspek.tɪv/",
        "Hearing feedback from international users gave us a fresh perspective.",
        ["viewpoint", "outlook"],
        ["blindness"],
    ),
    (
        "concise",
        "adjective",
        "Giving a lot of information clearly and in a few words; brief but comprehensive.",
        "/kənˈsaɪs/",
        "Keep your status update concise so the team can scan it quickly.",
        ["succinct", "brief"],
        ["wordy"],
    ),
    (
        "initiative",
        "noun",
        "The ability to assess and initiate things independently.",
        "/ɪˈnɪʃ.ə.tɪv/",
        "He showed great initiative by organizing the onboarding documentation.",
        ["enterprise", "drive"],
        ["apathy"],
    ),
    (
        "clarify",
        "verb",
        "To make a statement or situation less confused and more comprehensible.",
        "/ˈklær.ə.faɪ/",
        "Could you clarify the timeline for the second phase of the rollout?",
        ["explain", "illuminate"],
        ["confuse"],
    ),
    (
        "sustainable",
        "adjective",
        "Able to be maintained at a certain rate or level over the long term.",
        "/səˈsteɪ.nə.bəl/",
        "Fifteen minutes of focused practice a day is a sustainable habit.",
        ["viable", "enduring"],
        ["unsustainable"],
    ),
    (
        "milestone",
        "noun",
        "A significant stage or event in the development of something.",
        "/ˈmaɪl.stoʊn/",
        "Completing your first 21-day cycle is an important learning milestone.",
        ["landmark", "benchmark"],
        ["setback"],
    ),
]

SPEAKING_TOPICS: list[tuple[str, str, str]] = [
    ("Introducing Your Goals", "CONVERSATIONAL", "Share your main reasons for improving your English and how you plan to use it."),
    ("Describing Your Daily Routine", "CONVERSATIONAL", "Walk through a typical workday or study day and highlight your favorite part."),
    ("Explaining a Recent Challenge", "IMPROMPTU", "Describe a problem you solved recently and the steps you took."),
    ("Giving a Short Project Update", "PUBLIC_SPEAKING", "Present a 60-second update on a task or project as if speaking to colleagues."),
    ("Comparing Two Options", "CONVERSATIONAL", "Compare working remotely with working in an office and explain your preference."),
    ("Sharing a Memorable Trip", "CONVERSATIONAL", "Describe a place you visited that left a strong impression on you."),
    ("Pitching an Idea", "PUBLIC_SPEAKING", "Propose one improvement for your workplace, school, or community."),
]

WRITING_TOPICS: list[tuple[str, str, str]] = [
    ("Professional Introduction Email", "DESCRIPTIVE", "Write a clear, welcoming introduction message to a new colleague or study partner."),
    ("Reflecting on a Learning Goal", "NARRATIVE", "Describe a skill you learned in the past and what helped you succeed."),
    ("Remote vs. In-Person Collaboration", "OPINION", "Share your view on how teams can communicate effectively across locations."),
    ("Summarizing a Key Decision", "ARGUMENTATIVE", "Write a structured rationale for choosing one project priority over another."),
    ("Describing an Ideal Work Environment", "DESCRIPTIVE", "Explain the habits and environment that help you do your best work."),
    ("A Lesson from a Mistake", "NARRATIVE", "Write about a time something did not go as planned and what you took away from it."),
    ("Technology in Daily Learning", "ARGUMENTATIVE", "Discuss how digital tools can support consistent language practice."),
]


def build_curriculum_items(
    release_key: str = CURRICULUM_RELEASE,
) -> list[ContentItem]:
    """Build deterministic 21-day curriculum ContentItem rows for all CEFR bands."""
    items: list[ContentItem] = []

    for level in LEVELS:
        word_ids: list[UUID] = []
        for idx, (
            word,
            pos,
            definition,
            ipa,
            example,
            synonyms,
            antonyms,
        ) in enumerate(BASE_VOCAB_WORDS, start=1):
            word_id = uuid5(
                NAMESPACE_URL,
                f"talkfiesta:{release_key}:vocab_word:{level}:{idx}",
            )
            word_ids.append(word_id)
            items.append(
                ContentItem(
                    id=word_id,
                    release_key=release_key,
                    module="VOCABULARY",
                    kind="VOCAB_WORD",
                    status="PUBLISHED",
                    cefr_level=level,
                    title=word,
                    body={
                        "word": word,
                        "part_of_speech": pos,
                        "definition": definition,
                        "ipa": ipa,
                        "examples": [example],
                        "synonyms": synonyms,
                        "antonyms": antonyms,
                        "review_exercise": {
                            "prompt": f"Which definition best matches '{word}'?",
                            "choices": [
                                {"id": "a", "text": definition},
                                {
                                    "id": "b",
                                    "text": "To postpone a decision indefinitely.",
                                },
                                {
                                    "id": "c",
                                    "text": "A temporary pause in a schedule.",
                                },
                            ],
                        },
                    },
                    content_version=1,
                )
            )

        word_id_strings = [str(wid) for wid in word_ids]

        for day in range(1, 22):
            s_title, s_type, s_instructions = SPEAKING_TOPICS[
                (day - 1) % len(SPEAKING_TOPICS)
            ]
            speaking_id = uuid5(
                NAMESPACE_URL,
                f"talkfiesta:{release_key}:lesson:SPEAKING:{level}:GENERAL:{day}",
            )
            items.append(
                ContentItem(
                    id=speaking_id,
                    release_key=release_key,
                    module="SPEAKING",
                    kind="SPEAKING_LESSON",
                    status="PUBLISHED",
                    cycle=1,
                    day=day,
                    cefr_level=level,
                    goal_variant="GENERAL",
                    slot="CORE",
                    title=f"Day {day}: {s_title}",
                    body={
                        "description": s_instructions,
                        "estimated_minutes": 10,
                        "exercise_type": s_type,
                        "topic": s_title,
                        "instructions": s_instructions,
                        "target_duration_seconds": 60,
                        "preparation_seconds": 15,
                        "tips": [
                            "State your main point in the first sentence.",
                            "Include one concrete example from your experience.",
                            "Speak at a steady, natural pace.",
                        ],
                    },
                    content_version=1,
                )
            )

            vocab_id = uuid5(
                NAMESPACE_URL,
                f"talkfiesta:{release_key}:lesson:VOCABULARY:{level}:GENERAL:{day}",
            )
            items.append(
                ContentItem(
                    id=vocab_id,
                    release_key=release_key,
                    module="VOCABULARY",
                    kind="VOCABULARY_LESSON",
                    status="PUBLISHED",
                    cycle=1,
                    day=day,
                    cefr_level=level,
                    goal_variant="GENERAL",
                    slot="CORE",
                    title=f"Day {day}: Essential {level} Communication Vocabulary",
                    body={
                        "description": f"Practice 10 core {level} words in real-world contexts.",
                        "estimated_minutes": 10,
                        "word_content_ids": word_id_strings,
                        "exercises": [
                            {
                                "item_id": f"fb-{day}-1",
                                "type": "FILL_BLANK",
                                "prompt": "Our engineering and design teams ___ closely every sprint.",
                                "choices": [
                                    "collaborate",
                                    "clarify",
                                    "prioritize",
                                    "milestone",
                                ],
                                "correct_choice": "collaborate",
                            },
                            {
                                "item_id": f"md-{day}-2",
                                "type": "MATCH_DEFINITION",
                                "prompt": "Select the definition that best matches 'concise':",
                                "choices": [
                                    {
                                        "id": "a",
                                        "text": "Giving information clearly and in a few words.",
                                    },
                                    {
                                        "id": "b",
                                        "text": "Working jointly with others on a project.",
                                    },
                                    {
                                        "id": "c",
                                        "text": "A significant stage or event in development.",
                                    },
                                ],
                                "correct_choice_id": "a",
                            },
                            {
                                "item_id": f"uic-{day}-3",
                                "type": "USE_IN_CONTEXT",
                                "word_id": word_id_strings[0],
                                "prompt": "Write one complete sentence using the word 'collaborate'.",
                            },
                        ],
                    },
                    content_version=1,
                )
            )

            w_title, w_type, w_instructions = WRITING_TOPICS[
                (day - 1) % len(WRITING_TOPICS)
            ]
            writing_id = uuid5(
                NAMESPACE_URL,
                f"talkfiesta:{release_key}:lesson:WRITING:{level}:GENERAL:{day}",
            )
            items.append(
                ContentItem(
                    id=writing_id,
                    release_key=release_key,
                    module="WRITING",
                    kind="WRITING_LESSON",
                    status="PUBLISHED",
                    cycle=1,
                    day=day,
                    cefr_level=level,
                    goal_variant="GENERAL",
                    slot="CORE",
                    title=f"Day {day}: {w_title}",
                    body={
                        "description": w_instructions,
                        "estimated_minutes": 15,
                        "writing_type": w_type,
                        "instructions": w_instructions,
                        "target_word_count": 80,
                        "minimum_word_count": 30,
                        "maximum_word_count": 250,
                        "time_limit_minutes": 15,
                        "tips": [
                            "Open with a clear topic sentence.",
                            "Connect your ideas with transition words.",
                            "Review verb tenses before submitting.",
                        ],
                    },
                    content_version=1,
                )
            )

    return items


async def ensure_assessment_bank_seeded(
    session: AsyncSession, release_key: str | None = None
) -> int:
    """Idempotently insert missing placement-bank-v1 questions."""
    items = build_assessment_bank_items(release_key)
    existing_ids = set(
        await session.scalars(
            select(ContentItem.id).where(
                ContentItem.id.in_([item.id for item in items])
            )
        )
    )
    missing = [item for item in items if item.id not in existing_ids]
    if missing:
        session.add_all(missing)
        await session.flush()
    return len(missing)


async def ensure_curriculum_seeded(
    session: AsyncSession, release_key: str = CURRICULUM_RELEASE
) -> int:
    """Idempotently insert missing 21-day curriculum lessons and vocabulary words."""
    items = build_curriculum_items(release_key)
    existing_ids = set(
        await session.scalars(
            select(ContentItem.id).where(
                ContentItem.id.in_([item.id for item in items])
            )
        )
    )
    missing = [item for item in items if item.id not in existing_ids]
    if missing:
        session.add_all(missing)
        await session.flush()
    return len(missing)


def seed_assessment_bank_sync(
    session: Session, release_key: str | None = None
) -> int:
    """Synchronous helper for CLI seed script."""
    items = build_assessment_bank_items(release_key)
    existing_ids = set(
        session.scalars(
            select(ContentItem.id).where(
                ContentItem.id.in_([item.id for item in items])
            )
        )
    )
    missing = [item for item in items if item.id not in existing_ids]
    if missing:
        session.add_all(missing)
        session.commit()
    return len(missing)


def seed_curriculum_sync(
    session: Session, release_key: str = CURRICULUM_RELEASE
) -> int:
    """Synchronous helper for CLI seed script."""
    items = build_curriculum_items(release_key)
    existing_ids = set(
        session.scalars(
            select(ContentItem.id).where(
                ContentItem.id.in_([item.id for item in items])
            )
        )
    )
    missing = [item for item in items if item.id not in existing_ids]
    if missing:
        session.add_all(missing)
        session.commit()
    return len(missing)

