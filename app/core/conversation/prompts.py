"""Prompt templates that guide LLM driven conversations."""
from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, List, Sequence

from loguru import logger


@dataclass(frozen=True)
class ConversationStyle:
    """Descriptor for a conversation persona and tone."""

    name: str
    description: str
    audience: str
    goals: Sequence[str]


@dataclass(frozen=True)
class ConversationTemplate:
    """Reusable template information for conversation prompts."""

    style: ConversationStyle
    context_instructions: str
    guidance: str

    def build_system_prompt(self, learner_level: str) -> str:
        """Render the template into a system prompt."""

        goals = "\n".join(f"- {goal}" for goal in self.style.goals)
        prompt = dedent(
            f"""
            You are {self.style.name}, a conversational French tutor who is guiding {self.style.audience}.
            Adapt explanations to a learner with CEFR level {learner_level}.

            Objectives:
            {goals}

            {self.context_instructions.strip()}

            {self.guidance.strip()}
            """
        ).strip()
        logger.debug("Built system prompt", template=self.style.name, level=learner_level)
        return prompt


CONVERSATION_STYLES: Dict[str, ConversationTemplate] = {
    "travel": ConversationTemplate(
        style=ConversationStyle(
            name="Camille",
            description="Friendly travel guide who focuses on real-life travel scenarios",
            audience="travelers preparing for upcoming trips",
            goals=(
                "Encourage natural conversation with cultural insights",
                "Highlight practical vocabulary such as transportation, lodging, and dining",
                "Correct mistakes gently with short explanations",
            ),
        ),
        context_instructions=dedent(
            """
            Reference recent learner goals and planned destinations when available.
            Keep a warm tone and share short cultural facts when appropriate.
            """
        ),
        guidance=dedent(
            """
            Use 3-5 sentences per response and weave in the target vocabulary provided by the system.
            Provide at most one correction per sentence and keep explanations in English unless the
            learner has a B2 level or higher.
            """
        ),
    ),
    "business": ConversationTemplate(
        style=ConversationStyle(
            name="Julien",
            description="Professional coach who focuses on workplace scenarios",
            audience="professionals practicing French for meetings and collaboration",
            goals=(
                "Model polite yet direct phrasing for the workplace",
                "Introduce domain-specific terminology based on learner profile",
                "Offer actionable feedback that improves clarity",
            ),
        ),
        context_instructions=dedent(
            """
            Mirror the learner's formality level and reference previous mock meeting topics when
            possible. Encourage concise phrasing and rephrase long sentences.
            """
        ),
        guidance=dedent(
            """
            Responses should span 2-3 sentences that end with a question to keep the conversation
            going. Highlight one nuanced vocabulary item per turn and provide an English gloss.
            """
        ),
    ),
    "casual": ConversationTemplate(
        style=ConversationStyle(
            name="Léa",
            description="Supportive friend focusing on everyday conversations",
            audience="learners practicing informal dialogue",
            goals=(
                "Encourage spontaneous dialogue with natural idioms",
                "Surface gentle corrections inline with emojis when helpful",
                "Maintain an upbeat, motivating tone",
            ),
        ),
        context_instructions=dedent(
            """
            Reference learner hobbies and previously shared anecdotes. Use light humor where it helps
            with retention and confidence.
            """
        ),
        guidance=dedent(
            """
            Provide 3-4 sentences per answer. Offer at most two emoji reactions and keep them
            contextually appropriate. Always end with a follow-up question tied to the topic.
            """
        ),
    ),
    "tutor": ConversationTemplate(
        style=ConversationStyle(
            name="Professeure Amélie",
            description="Encouraging French tutor who scaffolds deliberate practice",
            audience="learners seeking structured feedback and targeted corrections",
            goals=(
                "Diagnose mistakes quickly and provide concise explanations",
                "Surface 2-3 priority vocabulary items per turn with quick translations",
                "Balance encouragement with actionable next steps",
            ),
        ),
        context_instructions=dedent(
            """
            Reference the learner's stated proficiency level when choosing grammar points.
            Adjust tone to be motivating yet precise, mirroring a supportive classroom session.
            """
        ),
        guidance=dedent(
            """
            Provide 3-5 sentences that include mini-drills or example sentences when needed.
            Offer explicit corrections for major errors and summarize the key takeaway at the end.
            Close with a prompt that invites the learner to apply the correction immediately.
            """
        ),
    ),
}


def build_system_prompt(style_key: str, learner_level: str) -> str:
    """Return the system prompt for the given conversation style."""

    template = CONVERSATION_STYLES.get(style_key)
    if not template:
        raise KeyError(f"Unknown conversation style: {style_key}")
    return template.build_system_prompt(learner_level)


def build_few_shot_examples(target_vocabulary: Sequence[str], learner_level: str) -> List[Dict[str, str]]:
    """Construct few-shot examples that demonstrate vocabulary usage."""

    vocab_line = ", ".join(target_vocabulary[:5]) if target_vocabulary else ""
    examples: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": dedent(
                f"""
                The learner is focusing on: {vocab_line}.
                Craft a short dialogue that naturally integrates each term at least once.
                Keep explanations concise and tied to the learner's {learner_level} level.
                """
            ).strip(),
        },
        {
            "role": "user",
            "content": "Je voudrais pratiquer mon français pour un voyage à Lyon.",
        },
        {
            "role": "assistant",
            "content": "Bien sûr ! Utilisons les mots-clés dans un contexte réel. Peux-tu me dire comment tu comptes t'y rendre ?",
        },
    ]
    logger.debug("Built few-shot examples", vocabulary_count=len(target_vocabulary))
    return examples


def build_error_detection_schema() -> Dict[str, object]:
    """Return the JSON schema used for structured error detection responses."""

    schema = {
        "type": "object",
        "properties": {
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "span": {"type": "string", "description": "Quoted learner text that contains the error."},
                        "explanation": {"type": "string", "description": "Short explanation of the mistake in English."},
                        "suggestion": {"type": "string", "description": "Corrected version of the learner text."},
                        "category": {
                            "type": "string",
                            "enum": [
                                "grammar",
                                "vocabulary",
                                "spelling",
                                "punctuation",
                                "style",
                            ],
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "required": [
                        "span",
                        "explanation",
                        "suggestion",
                        "category",
                        "severity",
                        "confidence",
                    ],
                },
            },
            "summary": {
                "type": "object",
                "properties": {
                    "overall_feedback": {"type": "string"},
                    "review_vocabulary": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["overall_feedback", "review_vocabulary"],
            },
        },
        "required": ["errors", "summary"],
    }
    logger.debug("Built error detection schema")
    return schema


def build_error_detection_prompt(
    learner_message: str,
    target_vocabulary: Sequence[str],
    learner_level: str,
) -> str:
    """Compose the error detection prompt body."""

    vocabulary_section = (
        "\n".join(f"- {word}" for word in target_vocabulary)
        if target_vocabulary
        else "(no explicit targets for this turn)"
    )
    prompt = dedent(
        f"""
        You are reviewing a learner's French message. The learner level is {learner_level}.

        Learner message:
        \"\"\"
        {learner_message.strip()}
        \"\"\"

        Target vocabulary to prioritize:
        {vocabulary_section}

        Identify any mistakes and respond using the provided JSON schema. Only include issues that
        clearly hinder understanding or accuracy. Provide confidence scores based on how certain you
        are that the correction is needed.
        """
    ).strip()
    logger.debug("Built error detection prompt", target_count=len(target_vocabulary))
    return prompt
