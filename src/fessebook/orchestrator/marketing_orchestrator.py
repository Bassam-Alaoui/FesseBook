"""
Orchestrateur Marketing Principal.

Ce module coordonne toutes les opérations de gestion des profils Facebook:
- Planification hebdomadaire
- Envoi des validations
- Rappels de publication
- Collecte des métriques
- Génération des rapports

IMPORTANT: Aucune publication automatique n'est effectuée.
Toute publication doit être réalisée manuellement par un humain.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fessebook.config import settings
from fessebook.models.profile import ClientProfile, ProfileStatus
from fessebook.models.post import Post, PostStatus
from fessebook.models.performance import Performance, PerformanceMetrics
from fessebook.models.report import (
    WeeklyReport,
    ProfileReport,
    ActionItem,
    ActionType,
    ActionPriority,
)
from fessebook.services.notion_service import NotionService
from fessebook.services.gmail_service import GmailService
from fessebook.services.content_generator import ContentGenerator

logger = logging.getLogger(__name__)


class MarketingOrchestrator:
    """
    Chef de projet marketing autonome augmenté par l'IA.

    Responsabilités:
    - Maintenir la régularité de publication
    - Améliorer l'engagement
    - Réduire la charge opérationnelle humaine
    - Fournir une vision centralisée de l'activité
    """

    def __init__(
        self,
        notion_service: Optional[NotionService] = None,
        gmail_service: Optional[GmailService] = None,
        content_generator: Optional[ContentGenerator] = None,
    ):
        """Initialise l'orchestrateur avec ses services."""
        self.notion = notion_service or NotionService()
        self.gmail = gmail_service or GmailService()
        self.content_generator = content_generator or ContentGenerator()

        self.admin_email = settings.gmail_sender_email

    # ===========================================
    # ANALYSE DE L'ÉTAT ACTUEL
    # ===========================================

    def analyze_current_state(self) -> dict:
        """
        Analyse l'état actuel du calendrier éditorial.

        Returns:
            Dictionnaire avec l'état complet et les actions prioritaires
        """
        logger.info("Analyse de l'état actuel du système...")

        # Récupérer les données
        all_profiles = self.notion.get_all_profiles()
        active_profiles = [p for p in all_profiles if p.status == ProfileStatus.ACTIVE]
        posts_to_validate = self.notion.get_posts_to_validate()
        posts_to_publish = self.notion.get_posts_to_publish_today()
        overdue_posts = self.notion.get_overdue_posts()
        profiles_needing_content = self.notion.get_profiles_needing_content()
        profiles_at_risk = self.notion.get_profiles_at_risk(days_threshold=7)

        # Construire l'analyse
        state = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_profiles": len(all_profiles),
                "active_profiles": len(active_profiles),
                "posts_awaiting_validation": len(posts_to_validate),
                "posts_to_publish_today": len(posts_to_publish),
                "overdue_posts": len(overdue_posts),
                "profiles_needing_content": len(profiles_needing_content),
                "profiles_at_risk": len(profiles_at_risk),
            },
            "profiles": {
                "all": all_profiles,
                "active": active_profiles,
                "needing_content": profiles_needing_content,
                "at_risk": profiles_at_risk,
            },
            "posts": {
                "to_validate": posts_to_validate,
                "to_publish_today": posts_to_publish,
                "overdue": overdue_posts,
            },
            "actions": [],
        }

        # Déterminer les actions prioritaires
        actions = []

        # Posts en retard (urgent)
        for post in overdue_posts:
            actions.append(ActionItem(
                type=ActionType.PUBLISH_POST,
                priority=ActionPriority.URGENT,
                profile_id=post.profile_id,
                profile_name=post.profile_name,
                description=f"Publication en retard de {(datetime.now() - post.scheduled_date).days} jours",
                due_date=datetime.now(),
            ))

        # Posts à publier aujourd'hui
        for post in posts_to_publish:
            actions.append(ActionItem(
                type=ActionType.PUBLISH_POST,
                priority=ActionPriority.HIGH,
                profile_id=post.profile_id,
                profile_name=post.profile_name,
                description=f"Publication prévue aujourd'hui à {post.scheduled_time}",
                due_date=datetime.now(),
            ))

        # Profils à risque
        for profile in profiles_at_risk:
            priority = ActionPriority.URGENT if profile.days_since_last_post and profile.days_since_last_post > 14 else ActionPriority.HIGH
            actions.append(ActionItem(
                type=ActionType.REACTIVATE_PROFILE,
                priority=priority,
                profile_id=profile.id,
                profile_name=profile.client_name,
                description=f"Inactif depuis {profile.days_since_last_post or 'N/A'} jours",
            ))

        # Profils nécessitant du contenu
        for profile in profiles_needing_content:
            if profile not in profiles_at_risk:  # Éviter les doublons
                actions.append(ActionItem(
                    type=ActionType.CREATE_CONTENT,
                    priority=ActionPriority.MEDIUM,
                    profile_id=profile.id,
                    profile_name=profile.client_name,
                    description="Planifier du nouveau contenu",
                ))

        # Posts à valider
        if posts_to_validate:
            actions.append(ActionItem(
                type=ActionType.VALIDATE_CONTENT,
                priority=ActionPriority.MEDIUM,
                description=f"{len(posts_to_validate)} posts en attente de validation",
            ))

        state["actions"] = sorted(actions, key=lambda a: (
            0 if a.priority == ActionPriority.URGENT else
            1 if a.priority == ActionPriority.HIGH else
            2 if a.priority == ActionPriority.MEDIUM else 3
        ))

        return state

    def get_priority_actions(self) -> list[ActionItem]:
        """Retourne uniquement les actions prioritaires."""
        state = self.analyze_current_state()
        return state["actions"]

    # ===========================================
    # 1. PLANIFICATION
    # ===========================================

    def run_weekly_planning(
        self,
        week_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> dict:
        """
        Exécute la planification hebdomadaire.

        - Détecte les profils sans contenu planifié
        - Génère des posts adaptés
        - Remplit le calendrier éditorial dans Notion

        Args:
            week_number: Numéro de la semaine (défaut: semaine suivante)
            year: Année (défaut: année courante)

        Returns:
            Résumé de la planification
        """
        now = datetime.now()
        if week_number is None:
            week_number = (now + timedelta(weeks=1)).isocalendar()[1]
        if year is None:
            year = now.year

        logger.info(f"Planification pour la semaine {week_number}/{year}")

        # Récupérer les profils actifs
        active_profiles = self.notion.get_active_profiles()

        # Pour chaque profil, vérifier le contenu planifié
        planning_results = {
            "week": week_number,
            "year": year,
            "profiles_processed": 0,
            "posts_created": 0,
            "posts_by_profile": {},
            "errors": [],
        }

        for profile in active_profiles:
            try:
                # Vérifier les posts déjà planifiés
                existing_posts = self.notion.get_posts_for_week(week_number, year)
                profile_posts = [p for p in existing_posts if p.profile_id == profile.id]

                # Calculer le nombre de posts manquants
                expected_posts = profile.get_posts_per_week()
                missing_posts = expected_posts - len(profile_posts)

                if missing_posts > 0:
                    logger.info(
                        f"Génération de {missing_posts} posts pour {profile.client_name}"
                    )

                    # Générer les posts
                    new_posts = self.content_generator.generate_week_content(
                        profile=profile,
                        week_number=week_number,
                        year=year,
                    )[:missing_posts]

                    # Créer les posts dans Notion
                    created_ids = []
                    for post in new_posts:
                        post_id = self.notion.create_post(post)
                        created_ids.append(post_id)

                    planning_results["posts_created"] += len(created_ids)
                    planning_results["posts_by_profile"][profile.client_name] = {
                        "existing": len(profile_posts),
                        "created": len(created_ids),
                        "total": len(profile_posts) + len(created_ids),
                    }

                planning_results["profiles_processed"] += 1

            except Exception as e:
                logger.error(f"Erreur lors de la planification pour {profile.client_name}: {e}")
                planning_results["errors"].append({
                    "profile": profile.client_name,
                    "error": str(e),
                })

        logger.info(
            f"Planification terminée: {planning_results['posts_created']} posts créés "
            f"pour {planning_results['profiles_processed']} profils"
        )

        return planning_results

    # ===========================================
    # 2. VALIDATION
    # ===========================================

    def send_validation_requests(self) -> dict:
        """
        Envoie les demandes de validation par email.

        Regroupe les posts par profil et responsable.

        Returns:
            Résumé des envois
        """
        logger.info("Envoi des demandes de validation...")

        # Récupérer les posts à valider
        posts_to_validate = self.notion.get_posts_to_validate()

        if not posts_to_validate:
            logger.info("Aucun post en attente de validation")
            return {"sent": 0, "posts": 0}

        # Regrouper par profil
        posts_by_profile: dict[str, list[Post]] = {}
        for post in posts_to_validate:
            if post.profile_id not in posts_by_profile:
                posts_by_profile[post.profile_id] = []
            posts_by_profile[post.profile_id].append(post)

        # Envoyer les emails
        results = {
            "sent": 0,
            "posts": len(posts_to_validate),
            "by_profile": {},
            "errors": [],
        }

        for profile_id, posts in posts_by_profile.items():
            try:
                # Récupérer les infos du profil
                profile = self.notion.get_profile_by_id(profile_id)
                if not profile:
                    continue

                # Déterminer le numéro de semaine
                week_number = posts[0].scheduled_date.isocalendar()[1]

                # Envoyer l'email
                success = self.gmail.send_validation_request(
                    to=profile.responsible_email,
                    posts=posts,
                    week_number=week_number,
                    profile_name=profile.client_name,
                )

                if success:
                    results["sent"] += 1
                    results["by_profile"][profile.client_name] = len(posts)

                    # Mettre à jour le statut dans Notion
                    for post in posts:
                        self.notion.update_post_status(post.id, PostStatus.TO_VALIDATE)

            except Exception as e:
                logger.error(f"Erreur lors de l'envoi pour le profil {profile_id}: {e}")
                results["errors"].append({"profile_id": profile_id, "error": str(e)})

        logger.info(f"Demandes de validation envoyées: {results['sent']}")
        return results

    def process_validation_response(
        self,
        profile_id: str,
        approved: bool,
        feedback: Optional[str] = None,
        validator_email: Optional[str] = None,
    ) -> bool:
        """
        Traite une réponse de validation.

        Args:
            profile_id: ID du profil concerné
            approved: True si validé, False si rejeté
            feedback: Commentaires ou raison du rejet
            validator_email: Email du validateur

        Returns:
            True si le traitement a réussi
        """
        posts = self.notion.get_posts_by_status(PostStatus.TO_VALIDATE)
        profile_posts = [p for p in posts if p.profile_id == profile_id]

        for post in profile_posts:
            if approved:
                post.mark_as_validated(validator_email or "unknown")
                self.notion.update_post_status(post.id, PostStatus.VALIDATED)
            else:
                post.mark_as_rejected(feedback or "Pas de raison spécifiée")
                self.notion.update_post_status(post.id, PostStatus.REJECTED)

        return True

    # ===========================================
    # 3. PUBLICATION GUIDÉE
    # ===========================================

    def send_publication_reminders(self) -> dict:
        """
        Envoie les rappels de publication pour les posts du jour.

        Returns:
            Résumé des rappels envoyés
        """
        logger.info("Envoi des rappels de publication...")

        # Posts validés prévus aujourd'hui
        posts_today = self.notion.get_posts_to_publish_today()

        if not posts_today:
            logger.info("Aucun post à publier aujourd'hui")
            return {"sent": 0, "posts": []}

        results = {
            "sent": 0,
            "posts": [],
            "errors": [],
        }

        for post in posts_today:
            try:
                # Récupérer le profil
                profile = self.notion.get_profile_by_id(post.profile_id)
                if not profile:
                    continue

                # Envoyer le rappel
                success = self.gmail.send_publication_reminder(
                    to=profile.responsible_email,
                    post=post,
                    facebook_profile_url=str(profile.facebook_profile_url),
                )

                if success:
                    results["sent"] += 1
                    results["posts"].append({
                        "profile": profile.client_name,
                        "scheduled_time": post.scheduled_time,
                    })

                    # Mettre à jour le statut
                    self.notion.update_post_status(post.id, PostStatus.TO_PUBLISH)

            except Exception as e:
                logger.error(f"Erreur lors du rappel pour le post {post.id}: {e}")
                results["errors"].append({"post_id": post.id, "error": str(e)})

        logger.info(f"Rappels de publication envoyés: {results['sent']}")
        return results

    def confirm_publication(
        self,
        post_id: str,
        confirmed_by: str,
        published_at: Optional[datetime] = None,
    ) -> bool:
        """
        Confirme qu'un post a été publié manuellement.

        Args:
            post_id: ID du post
            confirmed_by: Email de la personne qui a publié
            published_at: Date/heure de publication (défaut: maintenant)

        Returns:
            True si la confirmation a réussi
        """
        published_at = published_at or datetime.now()

        # Marquer comme publié dans Notion
        success = self.notion.mark_post_published(post_id, published_at, confirmed_by)

        if success:
            # Récupérer les infos du post pour mettre à jour le profil
            posts = self.notion.get_all_posts()
            post = next((p for p in posts if p.id == post_id), None)

            if post:
                # Mettre à jour la dernière publication du profil
                self.notion.update_profile_last_publication(
                    post.profile_id, published_at
                )

                # Créer une entrée de performance vide
                performance = Performance(
                    id="",
                    notion_page_id="",
                    post_id=post_id,
                    profile_id=post.profile_id,
                    profile_name=post.profile_name,
                    publication_date=published_at,
                    metrics=PerformanceMetrics(),
                    reported_by=confirmed_by,
                )
                self.notion.create_performance_entry(performance)

        return success

    # ===========================================
    # 4. SUIVI DE PERFORMANCE
    # ===========================================

    def send_metrics_requests(self) -> dict:
        """
        Envoie les demandes de métriques pour les posts publiés récemment.

        Envoie une demande 24-48h après publication.

        Returns:
            Résumé des demandes envoyées
        """
        logger.info("Envoi des demandes de métriques...")

        # Calculer la fenêtre temporelle
        now = datetime.now()
        min_published = now - timedelta(hours=72)  # Pas plus de 3 jours
        max_published = now - timedelta(hours=settings.metrics_request_delay_hours)

        # Récupérer les posts publiés récemment
        published_posts = self.notion.get_posts_by_status(PostStatus.PUBLISHED)

        # Filtrer par date de publication
        posts_needing_metrics = [
            p for p in published_posts
            if p.published_at and min_published <= p.published_at <= max_published
        ]

        results = {
            "sent": 0,
            "posts": [],
            "errors": [],
        }

        for post in posts_needing_metrics:
            try:
                # Vérifier si les métriques ont déjà été collectées
                perf = self.notion.get_performance_for_post(post.id)
                if perf and perf.metrics_collected_at:
                    continue  # Métriques déjà collectées

                # Récupérer le profil
                profile = self.notion.get_profile_by_id(post.profile_id)
                if not profile:
                    continue

                # Envoyer la demande
                success = self.gmail.send_metrics_request(
                    to=profile.responsible_email,
                    post=post,
                    published_at=post.published_at or datetime.now(),
                )

                if success:
                    results["sent"] += 1
                    results["posts"].append({
                        "profile": profile.client_name,
                        "published_at": post.published_at.isoformat() if post.published_at else "",
                    })

            except Exception as e:
                logger.error(f"Erreur lors de la demande de métriques pour {post.id}: {e}")
                results["errors"].append({"post_id": post.id, "error": str(e)})

        logger.info(f"Demandes de métriques envoyées: {results['sent']}")
        return results

    def record_metrics(
        self,
        post_id: str,
        metrics: PerformanceMetrics,
        observations: str = "",
        reported_by: str = "",
    ) -> bool:
        """
        Enregistre les métriques d'un post.

        Args:
            post_id: ID du post
            metrics: Métriques de performance
            observations: Observations qualitatives
            reported_by: Email de la personne qui rapporte

        Returns:
            True si l'enregistrement a réussi
        """
        # Récupérer ou créer l'entrée de performance
        perf = self.notion.get_performance_for_post(post_id)

        if perf:
            # Mettre à jour les métriques existantes
            return self.notion.update_performance_metrics(perf.id, metrics)
        else:
            # Créer une nouvelle entrée
            posts = self.notion.get_all_posts()
            post = next((p for p in posts if p.id == post_id), None)

            if not post:
                return False

            new_perf = Performance(
                id="",
                notion_page_id="",
                post_id=post_id,
                profile_id=post.profile_id,
                profile_name=post.profile_name,
                publication_date=post.published_at or datetime.now(),
                metrics=metrics,
                metrics_collected_at=datetime.now(),
                qualitative_observations=observations,
                reported_by=reported_by,
            )
            self.notion.create_performance_entry(new_perf)
            return True

    # ===========================================
    # 5. RAPPORTS
    # ===========================================

    def generate_weekly_report(
        self,
        week_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> WeeklyReport:
        """
        Génère le rapport hebdomadaire complet.

        Args:
            week_number: Numéro de la semaine (défaut: semaine courante)
            year: Année (défaut: année courante)

        Returns:
            Rapport hebdomadaire généré
        """
        now = datetime.now()
        if week_number is None:
            week_number = now.isocalendar()[1]
        if year is None:
            year = now.year

        logger.info(f"Génération du rapport pour la semaine {week_number}/{year}")

        # Calculer les dates de la semaine
        first_day_of_year = datetime(year, 1, 1)
        start_of_week = first_day_of_year + timedelta(weeks=week_number - 1)
        start_of_week = start_of_week - timedelta(days=start_of_week.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Créer le rapport
        report = WeeklyReport(
            week_number=week_number,
            year=year,
            period_start=start_of_week,
            period_end=end_of_week,
        )

        # Récupérer les données
        all_profiles = self.notion.get_all_profiles()
        week_posts = self.notion.get_posts_for_week(week_number, year)

        # Générer les rapports par profil
        for profile in all_profiles:
            profile_posts = [p for p in week_posts if p.profile_id == profile.id]
            published_posts = [p for p in profile_posts if p.status == PostStatus.PUBLISHED]

            # Récupérer les performances
            performances = self.notion.get_performances_for_profile(
                profile.id, start_of_week
            )

            # Calculer les totaux
            total_likes = sum(p.metrics.likes for p in performances)
            total_comments = sum(p.metrics.comments for p in performances)
            total_shares = sum(p.metrics.shares for p in performances)

            # Créer le rapport du profil
            profile_report = ProfileReport(
                profile_id=profile.id,
                profile_name=profile.client_name,
                responsible_person=profile.responsible_person,
                posts_planned=len(profile_posts),
                posts_published=len(published_posts),
                posts_pending=len([p for p in profile_posts if p.status in (
                    PostStatus.TO_VALIDATE, PostStatus.VALIDATED, PostStatus.TO_PUBLISH
                )]),
                posts_overdue=len([p for p in profile_posts if p.is_overdue()]),
                total_likes=total_likes,
                total_comments=total_comments,
                total_shares=total_shares,
                engagement_score=total_likes + total_comments * 2 + total_shares * 3,
                is_active=profile.status == ProfileStatus.ACTIVE,
                days_since_last_post=profile.days_since_last_post,
            )
            profile_report.risk_level = profile_report.calculate_risk_level()

            report.profile_reports.append(profile_report)

        # Calculer les statistiques globales
        report.calculate_statistics()

        # Générer les actions
        state = self.analyze_current_state()
        report.action_items = state["actions"][:10]  # Top 10 actions

        # Générer les insights
        report.key_insights = self._generate_insights(report)
        report.recommendations = self._generate_recommendations(report)

        return report

    def send_weekly_report(
        self,
        recipients: Optional[list[str]] = None,
        week_number: Optional[int] = None,
        year: Optional[int] = None,
    ) -> bool:
        """
        Génère et envoie le rapport hebdomadaire.

        Args:
            recipients: Liste des emails destinataires
            week_number: Numéro de la semaine
            year: Année

        Returns:
            True si l'envoi a réussi
        """
        report = self.generate_weekly_report(week_number, year)

        recipients = recipients or [self.admin_email]

        success = True
        for recipient in recipients:
            if not self.gmail.send_weekly_report(recipient, report):
                success = False

        return success

    def _generate_insights(self, report: WeeklyReport) -> list[str]:
        """Génère des insights basés sur le rapport."""
        insights = []

        # Taux de publication
        if report.publication_rate >= 90:
            insights.append("Excellent taux de publication cette semaine")
        elif report.publication_rate < 50:
            insights.append("Taux de publication faible - revoir l'organisation")

        # Profils à risque
        if report.profiles_at_risk:
            insights.append(
                f"{len(report.profiles_at_risk)} profils nécessitent une attention particulière"
            )

        # Engagement
        if report.average_engagement_per_post > 20:
            insights.append("Engagement supérieur à la moyenne")
        elif report.average_engagement_per_post < 5:
            insights.append("Engagement faible - revoir la stratégie de contenu")

        # Top performers
        if report.top_performers:
            best = report.top_performers[0]
            insights.append(
                f"Meilleure performance: {best.profile_name} avec un score de {best.engagement_score}"
            )

        return insights

    def _generate_recommendations(self, report: WeeklyReport) -> list[str]:
        """Génère des recommandations basées sur le rapport."""
        recommendations = []

        if report.publication_rate < 80:
            recommendations.append(
                "Planifier les publications plus en avance pour améliorer le taux"
            )

        if report.profiles_at_risk:
            recommendations.append(
                "Contacter les responsables des profils inactifs pour relancer l'activité"
            )

        if report.total_posts_overdue > 0:
            recommendations.append(
                f"Traiter en priorité les {report.total_posts_overdue} posts en retard"
            )

        if report.average_engagement_per_post < 10:
            recommendations.append(
                "Expérimenter avec des formats de contenu plus engageants (questions, sondages)"
            )

        return recommendations

    # ===========================================
    # ALERTES
    # ===========================================

    def send_inactivity_alerts(self) -> dict:
        """
        Envoie des alertes pour les profils inactifs.

        Returns:
            Résumé des alertes envoyées
        """
        logger.info("Vérification des profils inactifs...")

        profiles_at_risk = self.notion.get_profiles_at_risk(
            days_threshold=settings.inactivity_warning_days
        )

        results = {
            "alerts_sent": 0,
            "profiles": [],
        }

        for profile in profiles_at_risk:
            days_inactive = profile.days_since_last_post or 30

            # Envoyer l'alerte au responsable
            success = self.gmail.send_inactivity_alert(
                to=profile.responsible_email,
                profile_name=profile.client_name,
                days_inactive=days_inactive,
                last_post_date=profile.last_publication_date,
            )

            if success:
                results["alerts_sent"] += 1
                results["profiles"].append({
                    "name": profile.client_name,
                    "days_inactive": days_inactive,
                    "critical": days_inactive > settings.inactivity_critical_days,
                })

        logger.info(f"Alertes d'inactivité envoyées: {results['alerts_sent']}")
        return results

    def send_overdue_alerts(self) -> bool:
        """
        Envoie une alerte pour les posts en retard.

        Returns:
            True si l'alerte a été envoyée
        """
        overdue_posts = self.notion.get_overdue_posts()

        if not overdue_posts:
            return True

        return self.gmail.send_overdue_posts_alert(
            to=self.admin_email,
            overdue_posts=overdue_posts,
        )

    # ===========================================
    # ORCHESTRATION COMPLÈTE
    # ===========================================

    def run_daily_routine(self) -> dict:
        """
        Exécute la routine quotidienne complète.

        Returns:
            Résumé de toutes les opérations
        """
        logger.info("Démarrage de la routine quotidienne...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "state_analysis": None,
            "publication_reminders": None,
            "metrics_requests": None,
            "inactivity_alerts": None,
            "overdue_alerts": None,
        }

        # 1. Analyser l'état actuel
        results["state_analysis"] = self.analyze_current_state()

        # 2. Envoyer les rappels de publication
        results["publication_reminders"] = self.send_publication_reminders()

        # 3. Demander les métriques
        results["metrics_requests"] = self.send_metrics_requests()

        # 4. Envoyer les alertes d'inactivité
        results["inactivity_alerts"] = self.send_inactivity_alerts()

        # 5. Envoyer les alertes de retard
        results["overdue_alerts"] = {"sent": self.send_overdue_alerts()}

        logger.info("Routine quotidienne terminée")
        return results

    def run_weekly_routine(self) -> dict:
        """
        Exécute la routine hebdomadaire complète.

        Returns:
            Résumé de toutes les opérations
        """
        logger.info("Démarrage de la routine hebdomadaire...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "planning": None,
            "validation_requests": None,
            "weekly_report": None,
        }

        # 1. Planification de la semaine suivante
        results["planning"] = self.run_weekly_planning()

        # 2. Envoyer les demandes de validation
        results["validation_requests"] = self.send_validation_requests()

        # 3. Générer et envoyer le rapport
        results["weekly_report"] = {"sent": self.send_weekly_report()}

        logger.info("Routine hebdomadaire terminée")
        return results
