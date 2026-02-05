"""Modèle de données pour les rapports hebdomadaires."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActionPriority(str, Enum):
    """Priorité d'une action."""

    URGENT = "urgent"
    HIGH = "haute"
    MEDIUM = "moyenne"
    LOW = "basse"


class ActionType(str, Enum):
    """Type d'action à effectuer."""

    CREATE_CONTENT = "creer_contenu"
    VALIDATE_CONTENT = "valider_contenu"
    PUBLISH_POST = "publier_post"
    COLLECT_METRICS = "collecter_metriques"
    REVIEW_STRATEGY = "revoir_strategie"
    CONTACT_CLIENT = "contacter_client"
    REACTIVATE_PROFILE = "reactiver_profil"


class ActionItem(BaseModel):
    """Action à effectuer dans le plan d'action."""

    type: ActionType
    priority: ActionPriority
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    description: str
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None

    def to_markdown(self) -> str:
        """Convertit l'action en format markdown."""
        priority_emoji = {
            ActionPriority.URGENT: "🔴",
            ActionPriority.HIGH: "🟠",
            ActionPriority.MEDIUM: "🟡",
            ActionPriority.LOW: "🟢",
        }
        emoji = priority_emoji.get(self.priority, "⚪")
        profile_info = f" [{self.profile_name}]" if self.profile_name else ""
        due = f" (échéance: {self.due_date.strftime('%d/%m')})" if self.due_date else ""
        return f"{emoji} **{self.type.value}**{profile_info}: {self.description}{due}"


class ProfileReport(BaseModel):
    """Rapport individuel pour un profil."""

    profile_id: str
    profile_name: str
    responsible_person: str

    # Statistiques de la semaine
    posts_planned: int = 0
    posts_published: int = 0
    posts_pending: int = 0
    posts_overdue: int = 0

    # Performance
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    engagement_score: float = 0.0
    performance_trend: str = "stable"  # hausse, stable, baisse

    # Statut
    is_active: bool = True
    days_since_last_post: Optional[int] = None
    risk_level: str = "normal"  # normal, attention, critique

    # Insights
    top_content_type: Optional[str] = None
    recommendations: list[str] = Field(default_factory=list)

    def calculate_risk_level(self) -> str:
        """Calcule le niveau de risque d'inactivité."""
        if not self.is_active:
            return "critique"
        if self.days_since_last_post is None:
            return "critique"
        if self.days_since_last_post > 14:
            return "critique"
        if self.days_since_last_post > 7:
            return "attention"
        if self.posts_overdue > 0:
            return "attention"
        return "normal"


class WeeklyReport(BaseModel):
    """Rapport hebdomadaire global."""

    # Période
    week_number: int
    year: int
    period_start: datetime
    period_end: datetime
    generated_at: datetime = Field(default_factory=datetime.now)

    # Vue d'ensemble
    total_profiles: int = 0
    active_profiles: int = 0
    inactive_profiles: int = 0

    # Publications
    total_posts_planned: int = 0
    total_posts_published: int = 0
    total_posts_pending: int = 0
    total_posts_overdue: int = 0
    publication_rate: float = 0.0  # Pourcentage de posts publiés vs planifiés

    # Engagement global
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_messages: int = 0
    average_engagement_per_post: float = 0.0

    # Classements
    top_performers: list[ProfileReport] = Field(
        default_factory=list, description="Top 5 des profils les plus performants"
    )
    profiles_at_risk: list[ProfileReport] = Field(
        default_factory=list, description="Profils nécessitant une attention"
    )

    # Détail par profil
    profile_reports: list[ProfileReport] = Field(default_factory=list)

    # Plan d'action
    action_items: list[ActionItem] = Field(
        default_factory=list, description="Actions prioritaires pour la semaine"
    )

    # Insights globaux
    key_insights: list[str] = Field(
        default_factory=list, description="Points clés de la semaine"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommandations générales"
    )

    def calculate_statistics(self) -> None:
        """Calcule les statistiques globales à partir des rapports de profils."""
        if not self.profile_reports:
            return

        self.total_profiles = len(self.profile_reports)
        self.active_profiles = sum(1 for p in self.profile_reports if p.is_active)
        self.inactive_profiles = self.total_profiles - self.active_profiles

        self.total_posts_planned = sum(p.posts_planned for p in self.profile_reports)
        self.total_posts_published = sum(p.posts_published for p in self.profile_reports)
        self.total_posts_pending = sum(p.posts_pending for p in self.profile_reports)
        self.total_posts_overdue = sum(p.posts_overdue for p in self.profile_reports)

        if self.total_posts_planned > 0:
            self.publication_rate = (
                self.total_posts_published / self.total_posts_planned
            ) * 100

        self.total_likes = sum(p.total_likes for p in self.profile_reports)
        self.total_comments = sum(p.total_comments for p in self.profile_reports)
        self.total_shares = sum(p.total_shares for p in self.profile_reports)

        if self.total_posts_published > 0:
            total_engagement = (
                self.total_likes + self.total_comments * 2 + self.total_shares * 3
            )
            self.average_engagement_per_post = total_engagement / self.total_posts_published

        # Identifier les top performers et profils à risque
        sorted_by_engagement = sorted(
            self.profile_reports, key=lambda p: p.engagement_score, reverse=True
        )
        self.top_performers = sorted_by_engagement[:5]

        self.profiles_at_risk = [
            p for p in self.profile_reports if p.risk_level in ("attention", "critique")
        ]

    def to_markdown(self) -> str:
        """Génère le rapport au format Markdown."""
        lines = [
            f"# Rapport Hebdomadaire - Semaine {self.week_number}/{self.year}",
            "",
            f"**Période**: {self.period_start.strftime('%d/%m/%Y')} - {self.period_end.strftime('%d/%m/%Y')}",
            f"**Généré le**: {self.generated_at.strftime('%d/%m/%Y à %H:%M')}",
            "",
            "---",
            "",
            "## Résumé Global",
            "",
            f"- **Profils gérés**: {self.total_profiles} ({self.active_profiles} actifs, {self.inactive_profiles} inactifs)",
            f"- **Publications**: {self.total_posts_published}/{self.total_posts_planned} ({self.publication_rate:.1f}%)",
            f"- **En attente**: {self.total_posts_pending} | **En retard**: {self.total_posts_overdue}",
            "",
            "### Engagement Total",
            "",
            f"- Likes: {self.total_likes}",
            f"- Commentaires: {self.total_comments}",
            f"- Partages: {self.total_shares}",
            f"- Messages reçus: {self.total_messages}",
            f"- Engagement moyen/post: {self.average_engagement_per_post:.1f}",
            "",
        ]

        if self.top_performers:
            lines.extend([
                "## Top Performances",
                "",
            ])
            for i, p in enumerate(self.top_performers[:5], 1):
                lines.append(
                    f"{i}. **{p.profile_name}** - Score: {p.engagement_score:.1f} "
                    f"({p.total_likes} likes, {p.total_comments} commentaires)"
                )
            lines.append("")

        if self.profiles_at_risk:
            lines.extend([
                "## Profils Nécessitant Attention",
                "",
            ])
            for p in self.profiles_at_risk:
                risk_emoji = "🔴" if p.risk_level == "critique" else "🟠"
                lines.append(
                    f"{risk_emoji} **{p.profile_name}** - "
                    f"{p.days_since_last_post or 'N/A'} jours sans publication"
                )
            lines.append("")

        if self.action_items:
            lines.extend([
                "## Plan d'Action",
                "",
            ])
            for action in self.action_items:
                lines.append(f"- {action.to_markdown()}")
            lines.append("")

        if self.key_insights:
            lines.extend([
                "## Points Clés",
                "",
            ])
            for insight in self.key_insights:
                lines.append(f"- {insight}")
            lines.append("")

        if self.recommendations:
            lines.extend([
                "## Recommandations",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        return "\n".join(lines)

    def to_email_html(self) -> str:
        """Génère le rapport au format HTML pour email."""
        # Version simplifiée HTML
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h1 style="color: #1877f2;">Rapport Hebdomadaire - S{self.week_number}</h1>
            <p><strong>Période:</strong> {self.period_start.strftime('%d/%m')} - {self.period_end.strftime('%d/%m/%Y')}</p>

            <div style="background: #f0f2f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h2 style="margin-top: 0;">Résumé</h2>
                <ul>
                    <li>Profils actifs: {self.active_profiles}/{self.total_profiles}</li>
                    <li>Publications: {self.total_posts_published}/{self.total_posts_planned}</li>
                    <li>Engagement total: {self.total_likes + self.total_comments + self.total_shares}</li>
                </ul>
            </div>

            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <h2 style="margin-top: 0; color: #856404;">Actions Prioritaires</h2>
                <ul>
                    {"".join(f"<li>{a.description}</li>" for a in self.action_items[:5])}
                </ul>
            </div>
        </body>
        </html>
        """
