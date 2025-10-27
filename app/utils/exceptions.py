"""Custom exception classes and error handling utilities."""
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from loguru import logger


class ConversationalLearningException(Exception):
    """Base exception for the application."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DatabaseError(ConversationalLearningException):
    """Database operation errors."""
    pass


class ValidationError(ConversationalLearningException):
    """Data validation errors."""
    pass


class AuthenticationError(ConversationalLearningException):
    """Authentication and authorization errors."""
    pass


class LLMServiceError(ConversationalLearningException):
    """LLM service communication errors."""
    pass


class SessionError(ConversationalLearningException):
    """Learning session related errors."""
    pass


class ProgressError(ConversationalLearningException):
    """Progress tracking errors."""
    pass


def handle_database_error(error: Exception) -> HTTPException:
    """Handle database errors and return appropriate HTTP response."""
    logger.error(f"Database error: {error}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database operation failed. Please try again later."
    )


def handle_validation_error(error: ValidationError) -> HTTPException:
    """Handle validation errors."""
    logger.warning(f"Validation error: {error.message}")
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "message": error.message,
            "details": error.details
        }
    )


def handle_authentication_error(error: AuthenticationError) -> HTTPException:
    """Handle authentication errors."""
    logger.warning(f"Authentication error: {error.message}")
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error.message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def handle_llm_service_error(error: LLMServiceError) -> HTTPException:
    """Handle LLM service errors."""
    logger.error(f"LLM service error: {error.message}")
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="AI service is temporarily unavailable. Please try again later."
    )


def handle_session_error(error: SessionError) -> HTTPException:
    """Handle learning session errors."""
    logger.error(f"Session error: {error.message}")
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error.message
    )


def handle_progress_error(error: ProgressError) -> HTTPException:
    """Handle progress tracking errors."""
    logger.error(f"Progress error: {error.message}")
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error.message
    )