"""Modèle de données pour le suivi de performance."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EngagementLevel(str, Enum):
    """Niveau d'engagement qualitatif."""

    EXCELLENT = "excellent"
    GOOD = "bon"
    AVERAGE = "moyen"
    LOW = "faible"
    VERY_LOW = "tres_faible"


class PerformanceMetrics(BaseModel):
    """Métriques quantitatives d'un post."""

    likes: int = Field(default=0, ge=0, description="Nombre de likes/réactions")
    comments: int = Field(default=0, ge=0, description="Nombre de commentaires")
    shares: int = Field(default=0, ge=0, description="Nombre de partages")
    messages_received: int = Field(
        default=0, ge=0, description="Messages privés reçus suite au post"
    )
    profile_visits: Optional[int] = Field(
        None, ge=0, description="Visites du profil (si disponible)"
    )
    link_clicks: Optional[int] = Field(
        None, ge=0, description="Clics sur le lien (si applicable)"
    )

    @property
    def total_engagement(self) -> int:
        """Calcule l'engagement total."""
        return self.likes + self.comments * 2 + self.shares * 3

    @property
    def engagement_rate_estimate(self) -> float:
        """
        Estime un taux d'engagement.

        Note: Sans accès au reach, c'est une estimation basée
        sur des moyennes du marché.
        """
        # Estimation basée sur un reach moyen de 10% des contacts
        estimated_reach = 500  # Valeur par défaut
        if self.total_engagement == 0:
            return 0.0
        return (self.total_engagement / estimated_reach) * 100


class Performance(BaseModel):
    """
    Suivi de performance d'un post publié.

    Correspond à la base Notion "Performance".
    """

    # Identifiants
    id: str = Field(..., description="ID unique (ID Notion)")
    notion_page_id: str = Field(..., description="ID de la page Notion")

    # Liaison
    post_id: str = Field(..., description="ID du post concerné")
    profile_id: str = Field(..., description="ID du profil")
    profile_name: str = Field(..., description="Nom du profil")

    # Dates
    publication_date: datetime = Field(..., description="Date de publication effective")
    metrics_collected_at: Optional[datetime] = Field(
        None, description="Date de collecte des métriques"
    )

    # Métriques
    metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)

    # Analyse qualitative
    engagement_level: EngagementLevel = Field(
        default=EngagementLevel.AVERAGE, description="Niveau d'engagement qualitatif"
    )
    qualitative_observations: str = Field(
        default="", description="Observations qualitatives"
    )
    notable_comments: list[str] = Field(
        default_factory=list, description="Commentaires notables"
    )
    sentiment: str = Field(
        default="neutre", description="Sentiment général (positif/neutre/négatif)"
    )

    # Recommandations
    recommendations: list[str] = Field(
        default_factory=list, description="Recommandations pour les prochains posts"
    )
    content_insights: str = Field(
        default="", description="Insights sur le type de contenu"
    )

    # Comparaison
    compared_to_average: str = Field(
        default="", description="Comparaison avec la moyenne du profil"
    )
    is_top_performer: bool = Field(
        default=False, description="Fait partie des meilleurs posts"
    )

    # Métadonnées
    reported_by: str = Field(default="", description="Métriques rapportées par")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def calculate_engagement_level(self) -> EngagementLevel:
        """Calcule automatiquement le niveau d'engagement."""
        total = self.metrics.total_engagement

        if total >= 50:
            return EngagementLevel.EXCELLENT
        elif total >= 25:
            return EngagementLevel.GOOD
        elif total >= 10:
            return EngagementLevel.AVERAGE
        elif total >= 5:
            return EngagementLevel.LOW
        else:
            return EngagementLevel.VERY_LOW

    def generate_quick_insight(self) -> str:
        """Génère un insight rapide basé sur les métriques."""
        insights = []

        if self.metrics.comments > self.metrics.likes * 0.1:
            insights.append("Fort taux de commentaires - contenu engageant")
        if self.metrics.shares > 5:
            insights.append("Bon potentiel viral - contenu partageable")
        if self.metrics.messages_received > 0:
            insights.append(
                f"{self.metrics.messages_received} messages reçus - génère des leads"
            )
        if self.metrics.total_engagement < 5:
            insights.append("Faible engagement - revoir la stratégie de contenu")

        return " | ".join(insights) if insights else "Performance dans la moyenne"

    class Config:
        """Configuration Pydantic."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ProfilePerformanceSummary(BaseModel):
    """Résumé de performance pour un profil sur une période."""

    profile_id: str
    profile_name: str
    period_start: datetime
    period_end: datetime

    total_posts: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_messages: int = 0

    average_engagement: float = 0.0
    best_performing_post_id: Optional[str] = None
    worst_performing_post_id: Optional[str] = None

    engagement_trend: str = Field(
        default="stable", description="Tendance: hausse/stable/baisse"
    )
    recommendations: list[str] = Field(default_factory=list)

    def calculate_averages(self, performances: list[Performance]) -> None:
        """Calcule les moyennes à partir d'une liste de performances."""
        if not performances:
            return

        self.total_posts = len(performances)
        self.total_likes = sum(p.metrics.likes for p in performances)
        self.total_comments = sum(p.metrics.comments for p in performances)
        self.total_shares = sum(p.metrics.shares for p in performances)
        self.total_messages = sum(p.metrics.messages_received for p in performances)

        total_engagement = sum(p.metrics.total_engagement for p in performances)
        self.average_engagement = total_engagement / self.total_posts

        # Identifier les meilleurs/pires posts
        sorted_perfs = sorted(
            performances, key=lambda p: p.metrics.total_engagement, reverse=True
        )
        self.best_performing_post_id = sorted_perfs[0].post_id
        self.worst_performing_post_id = sorted_perfs[-1].post_id
