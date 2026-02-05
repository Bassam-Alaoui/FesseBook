"""Configuration centralisée de FesseBook."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration de l'application FesseBook."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # NOTION
    # ===========================================
    notion_token: str = Field(
        ..., description="Token d'intégration Notion"
    )
    notion_db_profiles: str = Field(
        ..., description="ID de la base Profils clients"
    )
    notion_db_calendar: str = Field(
        ..., description="ID de la base Calendrier éditorial"
    )
    notion_db_performance: str = Field(
        ..., description="ID de la base Performance"
    )

    # ===========================================
    # GMAIL
    # ===========================================
    gmail_credentials_path: Path = Field(
        default=Path("credentials.json"),
        description="Chemin vers le fichier credentials OAuth2",
    )
    gmail_token_path: Path = Field(
        default=Path("token.json"),
        description="Chemin vers le token d'authentification",
    )
    gmail_sender_email: str = Field(
        default="", description="Email expéditeur"
    )

    # ===========================================
    # HOOTSUITE (optionnel)
    # ===========================================
    hootsuite_api_key: Optional[str] = Field(
        default=None, description="Clé API Hootsuite"
    )
    hootsuite_api_secret: Optional[str] = Field(
        default=None, description="Secret API Hootsuite"
    )

    # ===========================================
    # APPLICATION
    # ===========================================
    log_level: str = Field(default="INFO", description="Niveau de log")
    timezone: str = Field(default="Europe/Paris", description="Fuseau horaire")
    publication_reminder_hours: int = Field(
        default=2, description="Heures avant rappel de publication"
    )
    metrics_request_delay_hours: int = Field(
        default=48, description="Heures après publication pour demander les métriques"
    )

    # ===========================================
    # GÉNÉRATION DE CONTENU (optionnel)
    # ===========================================
    openai_api_key: Optional[str] = Field(
        default=None, description="Clé API OpenAI"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Clé API Anthropic"
    )

    # ===========================================
    # SEUILS ET PARAMÈTRES
    # ===========================================
    inactivity_warning_days: int = Field(
        default=7, description="Jours sans post avant avertissement"
    )
    inactivity_critical_days: int = Field(
        default=14, description="Jours sans post avant alerte critique"
    )
    default_posts_per_week: int = Field(
        default=2, description="Nombre de posts par semaine par défaut"
    )

    @property
    def has_ai_content_generation(self) -> bool:
        """Vérifie si la génération de contenu IA est configurée."""
        return bool(self.openai_api_key or self.anthropic_api_key)

    @property
    def has_hootsuite(self) -> bool:
        """Vérifie si Hootsuite est configuré."""
        return bool(self.hootsuite_api_key and self.hootsuite_api_secret)


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance singleton des settings."""
    return Settings()


# Pour un accès direct
settings = get_settings()
