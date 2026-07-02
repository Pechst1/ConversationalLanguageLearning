"""Tests for uploaded-book ingestion helpers."""
from __future__ import annotations

import json

from app.services.book_parser import BookParserService


class _FakeLLMResult:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLMService:
    def generate_chat_completion(self, *args, **kwargs) -> _FakeLLMResult:
        return _FakeLLMResult(
            json.dumps(
                {
                    "scenes": [],
                    "characters": [],
                    "vocabulary": [],
                    "narration_a1": "",
                    "narration_b1": "",
                    "themes": [],
                }
            )
        )


def test_book_parser_cleans_pdf_style_noise(db_session) -> None:
    parser = BookParserService(db_session, llm_service=_FakeLLMService())

    cleaned = parser._clean_extracted_text(
        "\n".join(
            [
                "MY BOOK",
                "1",
                "The long hyphen-",
                "ated word continues.",
                "MY BOOK",
                "2",
                "A real paragraph stays here.",
                "MY BOOK",
                "3",
                "Another real paragraph stays here.",
                "MY BOOK",
            ]
        )
    )

    assert "hyphenated" in cleaned
    assert "1" not in cleaned
    assert "MY BOOK" not in cleaned
    assert "A real paragraph stays here." in cleaned


def test_parse_book_file_processes_all_chapters_when_uncapped(db_session) -> None:
    parser = BookParserService(db_session, llm_service=_FakeLLMService())
    repeated = "Une scène calme avec assez de texte pour dépasser le seuil. " * 4
    content = f"CHAPTER 1\n{repeated}\nCHAPTER 2\n{repeated}".encode()

    result = parser.parse_book_file(content, "sample.txt", max_chapters=None)

    assert len(result.chapters) == 2
    assert result.total_word_count > 0
