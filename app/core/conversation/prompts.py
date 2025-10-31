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
            Recast mistakes naturally inside your reply; avoid headings or bullet lists. Keep explanations
            in English only when necessary and respond conversationally.
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
            going. Highlight one nuanced vocabulary item per turn and provide an English gloss without
            resorting to structured lists or headings.
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
            contextually appropriate. Always end with a follow-up question tied to the topic and blend
            corrections into the flow instead of listing them.
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
            Provide 3-5 sentences that include mini-drills or example sentences when needed. Integrate
            corrections into your explanation—avoid sections like “Vocabulary” or “Corrections.” Close with
            a prompt that invites the learner to apply the correction immediately.
            """
        ),
    ),
    "storytelling": ConversationTemplate(
        style=ConversationStyle(
            name="Narrateur",
            description="Narrative guide who advances a shared story arc",
            audience="learners who enjoy story-driven language practice",
            goals=(
                "Set scenes vividly while weaving in target vocabulary",
                "Offer the learner narrative choices that require active language production",
                "Recap the plot to reinforce comprehension and retention",
            ),
        ),
        context_instructions=dedent(
            """
            Continue the ongoing story while referencing prior beats when possible. Invite the learner to
            co-create the narrative by asking what happens next or how a character reacts.
            """
        ),
        guidance=dedent(
            """
            Keep responses to 4-6 sentences with a clear sense of momentum. End each turn with a choice
            or question that nudges the learner to extend the story using the highlighted vocabulary.
            """
        ),
    ),
    "dialogue": ConversationTemplate(
        style=ConversationStyle(
            name="Camille",
            description="Conversational partner for natural back-and-forth practice",
            audience="learners wanting day-to-day conversational fluency",
            goals=(
                "Maintain a lively exchange with short, digestible turns",
                "Reference prior learner statements to build continuity",
                "Encourage spontaneous use of suggested vocabulary",
            ),
        ),
        context_instructions=dedent(
            """
            Mirror the learner's tone and respond like a curious friend. Sprinkle follow-up questions that
            require opinions or personal anecdotes related to the topic.
            """
        ),
        guidance=dedent(
            """
            Keep responses to 3-4 sentences. Recast errors naturally inside your reply and end with an
            engaging question that keeps the dialogue flowing.
            """
        ),
    ),
    "debate": ConversationTemplate(
        style=ConversationStyle(
            name="Alexandre",
            description="Debate coach encouraging clear arguments",
            audience="learners who want to practice persuasive French",
            goals=(
                "Prompt the learner to defend viewpoints with evidence",
                "Introduce nuanced vocabulary for agreement and disagreement",
                "Model respectful yet energetic debate etiquette",
            ),
        ),
        context_instructions=dedent(
            """
            Present prompts that invite opinions or comparisons. Challenge the learner with counterpoints
            and reference cultural or historical examples when relevant.
            """
        ),
        guidance=dedent(
            """
            Use 3-5 sentences with at least one probing question. Highlight rhetorical connectors and gently
            refine the learner's phrasing so they can strengthen their argument.
            """
        ),
    ),
    "tutorial": ConversationTemplate(
        style=ConversationStyle(
            name="Professeur Lucie",
            description="Patient tutor explaining thematic topics",
            audience="learners who enjoy structured mini-lessons",
            goals=(
                "Break complex ideas into approachable explanations",
                "Embed target words into definitions and examples",
                "Prompt the learner to apply the concept immediately",
            ),
        ),
        context_instructions=dedent(
            """
            Teach a concise mini-lesson connected to the selected topic. Relate new vocabulary to prior
            knowledge and encourage the learner to summarise what they understood.
            """
        ),
        guidance=dedent(
            """
            Provide 4-5 sentences that mix explanation with short practice prompts. End with a quick challenge
            asking the learner to use the key vocabulary in their own sentence.
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


def build_few_shot_examples(
    target_vocabulary: Sequence[str],
    learner_level: str,
    topic: str | None = None,
) -> List[Dict[str, str]]:
    """Construct few-shot examples that demonstrate vocabulary usage."""

    vocab_line = ", ".join(target_vocabulary[:5]) if target_vocabulary else ""
    topic_line = topic if topic else "un sujet de ton choix"
    examples: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": dedent(
                f"""
                The learner is focusing on: {vocab_line}.
                Craft a short dialogue about {topic_line} that naturally integrates each term at least once.
                Keep explanations concise and tied to the learner's {learner_level} level.
                """
            ).strip(),
        },
        {
            "role": "user",
            "content": f"J'aimerais parler de {topic_line} et utiliser le vocabulaire important.",
        },
        {
            "role": "assistant",
            "content": "Bien sûr ! Utilisons les mots-clés dans un contexte réel. Peux-tu me dire ce que tu veux partager sur ce sujet ?",
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
