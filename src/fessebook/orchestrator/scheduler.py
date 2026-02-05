"""Planificateur de tâches automatisées."""

import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from fessebook.config import settings
from fessebook.orchestrator.marketing_orchestrator import MarketingOrchestrator

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Planificateur des tâches automatisées FesseBook.

    Gère l'exécution automatique de:
    - Routine quotidienne (rappels, métriques, alertes)
    - Routine hebdomadaire (planification, validation, rapport)
    - Tâches personnalisées
    """

    def __init__(self, orchestrator: Optional[MarketingOrchestrator] = None):
        """Initialise le scheduler."""
        self.orchestrator = orchestrator or MarketingOrchestrator()
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        """Configure les tâches planifiées par défaut."""
        # Routine quotidienne - tous les jours à 8h00
        self.scheduler.add_job(
            self._run_daily_routine,
            CronTrigger(hour=8, minute=0),
            id="daily_routine",
            name="Routine quotidienne",
            replace_existing=True,
        )

        # Rappels de publication - 2h avant l'heure de publication par défaut (10h)
        # Donc à 8h pour des publications à 10h
        self.scheduler.add_job(
            self._send_publication_reminders,
            CronTrigger(hour=8, minute=0),
            id="publication_reminders",
            name="Rappels de publication",
            replace_existing=True,
        )

        # Second rappel à 9h30
        self.scheduler.add_job(
            self._send_publication_reminders,
            CronTrigger(hour=9, minute=30),
            id="publication_reminders_2",
            name="Rappels de publication (2ème)",
            replace_existing=True,
        )

        # Demande de métriques - tous les jours à 18h
        self.scheduler.add_job(
            self._send_metrics_requests,
            CronTrigger(hour=18, minute=0),
            id="metrics_requests",
            name="Demandes de métriques",
            replace_existing=True,
        )

        # Routine hebdomadaire - tous les lundis à 7h00
        self.scheduler.add_job(
            self._run_weekly_routine,
            CronTrigger(day_of_week="mon", hour=7, minute=0),
            id="weekly_routine",
            name="Routine hebdomadaire",
            replace_existing=True,
        )

        # Rapport hebdomadaire - tous les vendredis à 17h00
        self.scheduler.add_job(
            self._send_weekly_report,
            CronTrigger(day_of_week="fri", hour=17, minute=0),
            id="weekly_report",
            name="Rapport hebdomadaire",
            replace_existing=True,
        )

        # Vérification des profils inactifs - tous les jours à 9h
        self.scheduler.add_job(
            self._check_inactivity,
            CronTrigger(hour=9, minute=0),
            id="inactivity_check",
            name="Vérification inactivité",
            replace_existing=True,
        )

        logger.info("Tâches planifiées configurées")

    def start(self) -> None:
        """Démarre le scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler démarré")

    def stop(self) -> None:
        """Arrête le scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler arrêté")

    def add_custom_job(
        self,
        func: Callable,
        trigger: CronTrigger,
        job_id: str,
        name: str,
    ) -> None:
        """
        Ajoute une tâche personnalisée.

        Args:
            func: Fonction à exécuter
            trigger: Déclencheur Cron
            job_id: Identifiant unique
            name: Nom descriptif
        """
        self.scheduler.add_job(
            func,
            trigger,
            id=job_id,
            name=name,
            replace_existing=True,
        )
        logger.info(f"Tâche ajoutée: {name}")

    def remove_job(self, job_id: str) -> bool:
        """
        Supprime une tâche planifiée.

        Args:
            job_id: Identifiant de la tâche

        Returns:
            True si la suppression a réussi
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Tâche supprimée: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de la tâche {job_id}: {e}")
            return False

    def list_jobs(self) -> list[dict]:
        """
        Liste toutes les tâches planifiées.

        Returns:
            Liste des tâches avec leurs informations
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def run_job_now(self, job_id: str) -> bool:
        """
        Exécute une tâche immédiatement.

        Args:
            job_id: Identifiant de la tâche

        Returns:
            True si l'exécution a été déclenchée
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.func()
                logger.info(f"Tâche exécutée manuellement: {job_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche {job_id}: {e}")
            return False

    # ===========================================
    # FONCTIONS WRAPPER
    # ===========================================

    def _run_daily_routine(self) -> None:
        """Wrapper pour la routine quotidienne."""
        logger.info(f"[{datetime.now()}] Exécution de la routine quotidienne")
        try:
            result = self.orchestrator.run_daily_routine()
            logger.info(f"Routine quotidienne terminée: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de la routine quotidienne: {e}")

    def _run_weekly_routine(self) -> None:
        """Wrapper pour la routine hebdomadaire."""
        logger.info(f"[{datetime.now()}] Exécution de la routine hebdomadaire")
        try:
            result = self.orchestrator.run_weekly_routine()
            logger.info(f"Routine hebdomadaire terminée: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de la routine hebdomadaire: {e}")

    def _send_publication_reminders(self) -> None:
        """Wrapper pour l'envoi des rappels de publication."""
        logger.info(f"[{datetime.now()}] Envoi des rappels de publication")
        try:
            result = self.orchestrator.send_publication_reminders()
            logger.info(f"Rappels envoyés: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des rappels: {e}")

    def _send_metrics_requests(self) -> None:
        """Wrapper pour l'envoi des demandes de métriques."""
        logger.info(f"[{datetime.now()}] Envoi des demandes de métriques")
        try:
            result = self.orchestrator.send_metrics_requests()
            logger.info(f"Demandes envoyées: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des demandes: {e}")

    def _send_weekly_report(self) -> None:
        """Wrapper pour l'envoi du rapport hebdomadaire."""
        logger.info(f"[{datetime.now()}] Envoi du rapport hebdomadaire")
        try:
            result = self.orchestrator.send_weekly_report()
            logger.info(f"Rapport envoyé: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du rapport: {e}")

    def _check_inactivity(self) -> None:
        """Wrapper pour la vérification d'inactivité."""
        logger.info(f"[{datetime.now()}] Vérification des profils inactifs")
        try:
            result = self.orchestrator.send_inactivity_alerts()
            logger.info(f"Alertes envoyées: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'inactivité: {e}")
