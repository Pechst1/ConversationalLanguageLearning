"""Scenario registry and definitions for roleplay sessions."""
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass(slots=True)
class Scenario:
    """Definition of a roleplay scenario."""
    id: str
    title: str
    description: str
    roles: Dict[str, str]  # e.g., {"user": "Customer", "assistant": "Baker"}
    initial_prompt: str
    goals: List[str]
    difficulty_level: str = "A2"

# Default Scenarios
BAKERY_SCENARIO = Scenario(
    id="bakery_v1",
    title="The French Bakery",
    description="You are buying bread and pastries for a breakfast with friends.",
    roles={"user": "Customer", "assistant": "Baker"},
    initial_prompt="Bonjour ! Bienvenue à la Boulangerie Martin. Que puis-je vous servir aujourd'hui ?",
    goals=["Order a baguette", "Ask for the price", "Pay with card or cash"],
    difficulty_level="A1"
)

JOB_INTERVIEW_SCENARIO = Scenario(
    id="job_interview_v1",
    title="Job Interview",
    description="You are interviewing for a marketing position at a tech company in Paris.",
    roles={"user": "Candidate", "assistant": "Hiring Manager"},
    initial_prompt="Bonjour, merci d'être venu. Asseyez-vous, je vous en prie. Pouvez-vous vous présenter brièvement ?",
    goals=["Introduce yourself", "Describe your experience", "Ask a question about the role"],
    difficulty_level="B2"
)

MYSTERY_SCENARIO = Scenario(
    id="mystery_train_v1",
    title="Mystery on the TGV",
    description="You are a detective on a train. Someone has stolen a valuable painting.",
    roles={"user": "Detective", "assistant": "Witness (Conductor)"},
    initial_prompt="Inspecteur ! C'est terrible, le tableau a disparu de la cabine 4. J'ai vu quelqu'un courir vers le wagon-bar.",
    goals=["Ask for a description of the suspect", "Ask about the time of the theft", "Decide where to search next"],
    difficulty_level="B1"
)

SCENARIO_REGISTRY: Dict[str, Scenario] = {
    s.id: s for s in [BAKERY_SCENARIO, JOB_INTERVIEW_SCENARIO, MYSTERY_SCENARIO]
}

def get_scenario(scenario_id: str) -> Scenario | None:
    """Retrieve a scenario by ID."""
    return SCENARIO_REGISTRY.get(scenario_id)

def list_scenarios() -> List[Scenario]:
    """List all available scenarios."""
    return list(SCENARIO_REGISTRY.values())
