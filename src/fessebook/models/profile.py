"""Modèle de données pour les profils clients Facebook."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ProfileStatus(str, Enum):
    """Statut d'activité d'un profil."""

    ACTIVE = "actif"
    INACTIVE = "inactif"
    PAUSED = "en_pause"
    PENDING_SETUP = "en_configuration"


class ContentType(str, Enum):
    """Types de contenu attendus pour un profil."""

    PROFESSIONAL = "professionnel"
    PERSONAL_BRANDING = "personal_branding"
    LIFESTYLE = "lifestyle"
    EDUCATIONAL = "educatif"
    PROMOTIONAL = "promotionnel"
    ENGAGEMENT = "engagement"
    MIXED = "mixte"


class PublicationFrequency(str, Enum):
    """Fréquence de publication souhaitée."""

    DAILY = "quotidien"
    THREE_PER_WEEK = "3_par_semaine"
    TWO_PER_WEEK = "2_par_semaine"
    WEEKLY = "hebdomadaire"
    BIWEEKLY = "bi_mensuel"


class ClientProfile(BaseModel):
    """
    Représente un profil client Facebook à gérer.

    Correspond à la base Notion "Profils clients".
    """

    # Identifiants
    id: str = Field(..., description="ID unique du profil (ID Notion)")
    notion_page_id: str = Field(..., description="ID de la page Notion")

    # Informations client
    client_name: str = Field(..., description="Nom du client")
    facebook_profile_url: HttpUrl = Field(..., description="Lien du profil Facebook")
    facebook_profile_id: Optional[str] = Field(None, description="ID Facebook si connu")

    # Gestion interne
    responsible_person: str = Field(..., description="Responsable interne assigné")
    responsible_email: str = Field(..., description="Email du responsable")

    # Configuration éditoriale
    content_type: ContentType = Field(
        default=ContentType.MIXED, description="Type de contenu attendu"
    )
    publication_frequency: PublicationFrequency = Field(
        default=PublicationFrequency.TWO_PER_WEEK, description="Fréquence de publication"
    )
    preferred_posting_days: list[str] = Field(
        default_factory=lambda: ["mardi", "jeudi"],
        description="Jours préférés de publication",
    )
    preferred_posting_time: str = Field(
        default="10:00", description="Heure préférée de publication (HH:MM)"
    )

    # Personnalisation du ton
    tone_description: str = Field(
        default="", description="Description du ton à adopter pour ce profil"
    )
    topics_of_interest: list[str] = Field(
        default_factory=list, description="Thématiques d'intérêt du profil"
    )
    hashtags: list[str] = Field(
        default_factory=list, description="Hashtags récurrents à utiliser"
    )
    avoid_topics: list[str] = Field(
        default_factory=list, description="Sujets à éviter"
    )

    # Statut
    status: ProfileStatus = Field(
        default=ProfileStatus.ACTIVE, description="Statut d'activité"
    )
    last_publication_date: Optional[datetime] = Field(
        None, description="Date de la dernière publication"
    )
    days_since_last_post: Optional[int] = Field(
        None, description="Nombre de jours depuis le dernier post"
    )

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: str = Field(default="", description="Notes additionnelles")

    def is_overdue(self, threshold_days: int = 7) -> bool:
        """Vérifie si le profil est en retard de publication."""
        if self.days_since_last_post is None:
            return True
        return self.days_since_last_post > threshold_days

    def needs_content(self) -> bool:
        """Vérifie si le profil a besoin de nouveau contenu planifié."""
        return self.status == ProfileStatus.ACTIVE and self.is_overdue()

    def get_posts_per_week(self) -> int:
        """Retourne le nombre de posts par semaine attendus."""
        frequency_map = {
            PublicationFrequency.DAILY: 7,
            PublicationFrequency.THREE_PER_WEEK: 3,
            PublicationFrequency.TWO_PER_WEEK: 2,
            PublicationFrequency.WEEKLY: 1,
            PublicationFrequency.BIWEEKLY: 0.5,
        }
        return int(frequency_map.get(self.publication_frequency, 2))

    class Config:
        """Configuration Pydantic."""

        json_encoders = {datetime: lambda v: v.isoformat()}
