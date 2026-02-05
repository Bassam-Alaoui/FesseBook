"""Configuration pytest pour FesseBook."""

import os
import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    """Configure l'environnement de test."""
    # Définir des variables d'environnement de test
    os.environ.setdefault("NOTION_TOKEN", "test_token")
    os.environ.setdefault("NOTION_DB_PROFILES", "test_db_profiles")
    os.environ.setdefault("NOTION_DB_CALENDAR", "test_db_calendar")
    os.environ.setdefault("NOTION_DB_PERFORMANCE", "test_db_performance")
    os.environ.setdefault("GMAIL_SENDER_EMAIL", "test@example.com")

    yield

    # Cleanup si nécessaire


@pytest.fixture
def mock_notion_client(mocker):
    """Mock du client Notion."""
    return mocker.patch("fessebook.services.notion_service.Client")


@pytest.fixture
def mock_gmail_service(mocker):
    """Mock du service Gmail."""
    return mocker.patch("fessebook.services.gmail_service.build")
