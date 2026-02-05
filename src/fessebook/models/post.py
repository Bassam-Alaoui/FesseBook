"""Modèle de données pour les posts du calendrier éditorial."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PostStatus(str, Enum):
    """Statut d'un post dans le workflow éditorial."""

    TO_GENERATE = "a_generer"
    TO_VALIDATE = "a_valider"
    VALIDATED = "valide"
    TO_PUBLISH = "a_publier"
    PUBLISHED = "publie"
    OVERDUE = "en_retard"
    REJECTED = "rejete"
    ARCHIVED = "archive"


class MediaType(str, Enum):
    """Type de média associé au post."""

    NONE = "aucun"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    LINK = "lien"


class PostMedia(BaseModel):
    """Média associé à un post."""

    type: MediaType = Field(default=MediaType.NONE)
    url: Optional[str] = Field(None, description="URL du média")
    file_path: Optional[str] = Field(None, description="Chemin local du fichier")
    description: str = Field(default="", description="Description/alt text du média")
    suggestion: str = Field(
        default="", description="Suggestion de média si non fourni"
    )


class Post(BaseModel):
    """
    Représente un post planifié dans le calendrier éditorial.

    Correspond à la base Notion "Calendrier éditorial".
    """

    # Identifiants
    id: str = Field(..., description="ID unique du post (ID Notion)")
    notion_page_id: str = Field(..., description="ID de la page Notion")

    # Liaison au profil
    profile_id: str = Field(..., description="ID du profil client concerné")
    profile_name: str = Field(..., description="Nom du profil pour référence rapide")

    # Planification
    scheduled_date: datetime = Field(..., description="Date de publication prévue")
    scheduled_time: str = Field(
        default="10:00", description="Heure de publication prévue (HH:MM)"
    )

    # Contenu
    content: str = Field(..., description="Texte du post")
    content_objective: str = Field(
        default="", description="Objectif du post (engagement, notoriété, etc.)"
    )
    call_to_action: str = Field(
        default="", description="Appel à l'action inclus dans le post"
    )

    # Média
    media: PostMedia = Field(default_factory=PostMedia)

    # Workflow
    status: PostStatus = Field(
        default=PostStatus.TO_GENERATE, description="Statut actuel du post"
    )
    validation_requested_at: Optional[datetime] = Field(
        None, description="Date de demande de validation"
    )
    validated_at: Optional[datetime] = Field(None, description="Date de validation")
    validated_by: Optional[str] = Field(None, description="Validé par (email)")
    published_at: Optional[datetime] = Field(
        None, description="Date/heure effective de publication"
    )
    publication_confirmed_by: Optional[str] = Field(
        None, description="Publication confirmée par"
    )

    # Feedback
    rejection_reason: Optional[str] = Field(
        None, description="Raison du rejet si applicable"
    )
    modification_notes: str = Field(
        default="", description="Notes de modification demandées"
    )

    # Métriques attendues
    expected_engagement: str = Field(
        default="", description="Indicateur de succès attendu"
    )

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system", description="Créé par (agent/humain)")

    # Lien vers la performance (après publication)
    performance_id: Optional[str] = Field(
        None, description="ID de l'entrée performance associée"
    )

    def is_overdue(self) -> bool:
        """Vérifie si le post est en retard."""
        if self.status == PostStatus.PUBLISHED:
            return False
        return datetime.now() > self.scheduled_date

    def is_ready_to_publish(self) -> bool:
        """Vérifie si le post est prêt à être publié."""
        return self.status == PostStatus.VALIDATED or self.status == PostStatus.TO_PUBLISH

    def needs_validation(self) -> bool:
        """Vérifie si le post attend une validation."""
        return self.status == PostStatus.TO_VALIDATE

    def get_copyable_content(self) -> str:
        """
        Retourne le contenu formaté prêt à être copié-collé.

        Inclut le texte et les instructions pour le média.
        """
        content_parts = [self.content]

        if self.media.type != MediaType.NONE:
            content_parts.append("")
            content_parts.append(f"--- MEDIA ({self.media.type.value}) ---")
            if self.media.url:
                content_parts.append(f"URL: {self.media.url}")
            if self.media.file_path:
                content_parts.append(f"Fichier: {self.media.file_path}")
            if self.media.suggestion:
                content_parts.append(f"Suggestion: {self.media.suggestion}")

        return "\n".join(content_parts)

    def mark_as_validated(self, validator_email: str) -> None:
        """Marque le post comme validé."""
        self.status = PostStatus.VALIDATED
        self.validated_at = datetime.now()
        self.validated_by = validator_email
        self.updated_at = datetime.now()

    def mark_as_published(self, confirmed_by: str) -> None:
        """Marque le post comme publié."""
        self.status = PostStatus.PUBLISHED
        self.published_at = datetime.now()
        self.publication_confirmed_by = confirmed_by
        self.updated_at = datetime.now()

    def mark_as_rejected(self, reason: str) -> None:
        """Marque le post comme rejeté."""
        self.status = PostStatus.REJECTED
        self.rejection_reason = reason
        self.updated_at = datetime.now()

    class Config:
        """Configuration Pydantic."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class PostBatch(BaseModel):
    """Groupe de posts pour une validation groupée."""

    profile_id: str
    profile_name: str
    week_number: int
    year: int
    posts: list[Post]
    total_posts: int = Field(default=0)

    def __init__(self, **data):
        super().__init__(**data)
        self.total_posts = len(self.posts)
