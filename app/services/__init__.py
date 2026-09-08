"""Service layer package."""

from importlib import import_module

__all__ = [
    "AchievementService",
    "AnalyticsService",
    "AuthService",
    "InsightsService",
    "LLMService",
    "ProgressService",
    "SessionService",
    "UserService",
    "VocabularyService",
]

_SERVICE_IMPORTS = {
    "AchievementService": ("app.services.achievement", "AchievementService"),
    "AnalyticsService": ("app.services.analytics", "AnalyticsService"),
    "AuthService": ("app.services.auth", "AuthService"),
    "InsightsService": ("app.services.insights_service", "InsightsService"),
    "LLMService": ("app.services.llm_service", "LLMService"),
    "ProgressService": ("app.services.progress", "ProgressService"),
    "SessionService": ("app.services.session_service", "SessionService"),
    "UserService": ("app.services.users", "UserService"),
    "VocabularyService": ("app.services.vocabulary", "VocabularyService"),
}


def __getattr__(name: str):
    """Load public service classes lazily to avoid package import cycles."""
    try:
        module_name, attribute_name = _SERVICE_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
