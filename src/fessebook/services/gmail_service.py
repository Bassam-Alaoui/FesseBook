"""Service d'intégration Gmail pour les notifications et communications."""

import base64
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from fessebook.config import settings
from fessebook.models.post import Post, PostBatch
from fessebook.models.report import WeeklyReport

logger = logging.getLogger(__name__)

# Scopes nécessaires pour Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailService:
    """
    Service de gestion des emails via Gmail API.

    Responsabilités:
    - Envoi des demandes de validation
    - Rappels de publication
    - Rapports hebdomadaires
    - Demandes de métriques
    """

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        token_path: Optional[Path] = None,
    ):
        """Initialise le service Gmail."""
        self.credentials_path = credentials_path or settings.gmail_credentials_path
        self.token_path = token_path or settings.gmail_token_path
        self.sender_email = settings.gmail_sender_email
        self.service = None

    def authenticate(self) -> bool:
        """
        Authentifie l'application avec Gmail.

        Utilise OAuth2 avec un flow d'installation si nécessaire.
        """
        creds = None

        # Charger les credentials existants
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # Renouveler ou créer les credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    logger.error(
                        f"Fichier credentials non trouvé: {self.credentials_path}"
                    )
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Sauvegarder le token
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        return True

    def _create_message(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> dict:
        """Crée un message email encodé."""
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["from"] = self.sender_email
        message["subject"] = subject

        # Version texte
        part1 = MIMEText(body_text, "plain", "utf-8")
        message.attach(part1)

        # Version HTML si fournie
        if body_html:
            part2 = MIMEText(body_html, "html", "utf-8")
            message.attach(part2)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}

    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """Envoie un email."""
        if not self.service:
            if not self.authenticate():
                return False

        try:
            message = self._create_message(to, subject, body_text, body_html)
            self.service.users().messages().send(
                userId="me", body=message
            ).execute()
            logger.info(f"Email envoyé à {to}: {subject}")
            return True
        except HttpError as e:
            logger.error(f"Erreur lors de l'envoi de l'email: {e}")
            return False

    # ===========================================
    # EMAILS DE VALIDATION
    # ===========================================

    def send_validation_request(
        self,
        to: str,
        posts: list[Post],
        week_number: int,
        profile_name: str,
    ) -> bool:
        """
        Envoie une demande de validation pour un groupe de posts.

        Args:
            to: Email du destinataire (responsable)
            posts: Liste des posts à valider
            week_number: Numéro de la semaine
            profile_name: Nom du profil concerné
        """
        subject = f"[FesseBook] Validation requise - {profile_name} - Semaine {week_number}"

        # Corps texte
        body_text = f"""Bonjour,

Voici les publications proposées pour le profil "{profile_name}" pour la semaine {week_number}.

Merci de valider ou de demander des modifications.

"""
        for i, post in enumerate(posts, 1):
            body_text += f"""
---
POST {i} - Prévu le {post.scheduled_date.strftime('%d/%m/%Y à %H:%M')}
---
{post.content}

Objectif: {post.content_objective}
Média suggéré: {post.media.suggestion or 'Aucun'}
"""

        body_text += """
---

Pour valider, répondez simplement "OK" ou "Validé".
Pour demander des modifications, décrivez les changements souhaités.

Cordialement,
L'équipe FesseBook
"""

        # Corps HTML
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: #1877f2; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Validation Requise</h1>
                <p style="margin: 5px 0 0 0;">{profile_name} - Semaine {week_number}</p>
            </div>

            <div style="padding: 20px;">
                <p>Bonjour,</p>
                <p>Voici les publications proposées pour validation:</p>
        """

        for i, post in enumerate(posts, 1):
            body_html += f"""
                <div style="background: #f0f2f5; border-radius: 8px; padding: 15px; margin: 15px 0;">
                    <div style="color: #65676b; font-size: 12px; margin-bottom: 10px;">
                        POST {i} - {post.scheduled_date.strftime('%d/%m/%Y à %H:%M')}
                    </div>
                    <div style="background: white; padding: 15px; border-radius: 8px; white-space: pre-wrap;">
{post.content}
                    </div>
                    <div style="margin-top: 10px; font-size: 13px; color: #65676b;">
                        <strong>Objectif:</strong> {post.content_objective}<br>
                        <strong>Média:</strong> {post.media.suggestion or 'Aucun suggéré'}
                    </div>
                </div>
            """

        body_html += """
                <div style="background: #e7f3ff; border-left: 4px solid #1877f2; padding: 15px; margin-top: 20px;">
                    <strong>Actions requises:</strong>
                    <ul>
                        <li>Répondez <strong>"OK"</strong> ou <strong>"Validé"</strong> pour approuver</li>
                        <li>Décrivez vos modifications si nécessaire</li>
                    </ul>
                </div>
            </div>

            <div style="background: #f0f2f5; padding: 15px; text-align: center; color: #65676b; font-size: 12px;">
                Cet email a été généré automatiquement par FesseBook
            </div>
        </body>
        </html>
        """

        return self.send_email(to, subject, body_text, body_html)

    # ===========================================
    # RAPPELS DE PUBLICATION
    # ===========================================

    def send_publication_reminder(
        self,
        to: str,
        post: Post,
        facebook_profile_url: str,
    ) -> bool:
        """
        Envoie un rappel de publication avec le contenu prêt à copier-coller.

        Args:
            to: Email du responsable de la publication
            post: Le post à publier
            facebook_profile_url: URL du profil Facebook
        """
        subject = f"[FesseBook] À publier maintenant - {post.profile_name}"

        body_text = f"""Bonjour,

Il est temps de publier sur le profil "{post.profile_name}".

PROFIL FACEBOOK:
{facebook_profile_url}

TEXTE À COPIER-COLLER:
-----------------------
{post.content}
-----------------------

"""
        if post.media.suggestion:
            body_text += f"""MÉDIA SUGGÉRÉ:
{post.media.suggestion}

"""
        if post.media.url:
            body_text += f"""URL DU MÉDIA:
{post.media.url}

"""

        body_text += """
Une fois la publication effectuée, merci de répondre "Publié" à cet email.

Cordialement,
L'équipe FesseBook
"""

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: #42b72a; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Publication à Effectuer</h1>
                <p style="margin: 5px 0 0 0;">{post.profile_name}</p>
            </div>

            <div style="padding: 20px;">
                <div style="background: #e7f3ff; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                    <strong>Profil Facebook:</strong><br>
                    <a href="{facebook_profile_url}" style="color: #1877f2;">{facebook_profile_url}</a>
                </div>

                <div style="background: #f0f2f5; border-radius: 8px; padding: 15px;">
                    <p style="font-weight: bold; margin-top: 0;">Texte à copier-coller:</p>
                    <div style="background: white; padding: 15px; border-radius: 8px; border: 2px dashed #1877f2; white-space: pre-wrap;">
{post.content}
                    </div>
                </div>
        """

        if post.media.suggestion or post.media.url:
            body_html += f"""
                <div style="margin-top: 15px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                    <strong>Média:</strong><br>
                    {post.media.suggestion or ''}<br>
                    {f'<a href="{post.media.url}">Télécharger le média</a>' if post.media.url else ''}
                </div>
            """

        body_html += """
                <div style="background: #42b72a; color: white; padding: 15px; border-radius: 8px; margin-top: 20px; text-align: center;">
                    <strong>Une fois publié, répondez "Publié" à cet email</strong>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(to, subject, body_text, body_html)

    # ===========================================
    # DEMANDES DE MÉTRIQUES
    # ===========================================

    def send_metrics_request(
        self,
        to: str,
        post: Post,
        published_at: datetime,
    ) -> bool:
        """
        Demande les métriques de performance après publication.

        Args:
            to: Email du responsable
            post: Le post publié
            published_at: Date de publication
        """
        subject = f"[FesseBook] Métriques requises - {post.profile_name}"

        body_text = f"""Bonjour,

Le post suivant a été publié le {published_at.strftime('%d/%m/%Y à %H:%M')} sur le profil "{post.profile_name}".

Merci de nous communiquer les métriques actuelles:

Post publié:
"{post.content[:200]}..."

Métriques à renseigner:
- Nombre de likes/réactions:
- Nombre de commentaires:
- Nombre de partages:
- Messages privés reçus (si applicable):
- Observations particulières:

Répondez simplement à cet email avec les informations.

Cordialement,
L'équipe FesseBook
"""

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: #f7931e; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">Métriques Requises</h1>
                <p style="margin: 5px 0 0 0;">{post.profile_name} - Publié le {published_at.strftime('%d/%m')}</p>
            </div>

            <div style="padding: 20px;">
                <div style="background: #f0f2f5; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <p style="font-weight: bold; margin-top: 0;">Post concerné:</p>
                    <p style="font-style: italic;">"{post.content[:200]}..."</p>
                </div>

                <div style="background: white; border: 1px solid #ddd; border-radius: 8px; padding: 20px;">
                    <p style="font-weight: bold; margin-top: 0;">Merci de renseigner:</p>
                    <ul>
                        <li>Nombre de likes/réactions: <strong>___</strong></li>
                        <li>Nombre de commentaires: <strong>___</strong></li>
                        <li>Nombre de partages: <strong>___</strong></li>
                        <li>Messages privés reçus: <strong>___</strong></li>
                        <li>Observations: <strong>___</strong></li>
                    </ul>
                </div>

                <p style="color: #65676b; font-size: 13px; margin-top: 20px;">
                    Répondez simplement à cet email avec les informations demandées.
                </p>
            </div>
        </body>
        </html>
        """

        return self.send_email(to, subject, body_text, body_html)

    # ===========================================
    # RAPPORTS
    # ===========================================

    def send_weekly_report(
        self,
        to: str,
        report: WeeklyReport,
    ) -> bool:
        """
        Envoie le rapport hebdomadaire.

        Args:
            to: Email du destinataire
            report: Le rapport hebdomadaire généré
        """
        subject = f"[FesseBook] Rapport Hebdomadaire - Semaine {report.week_number}/{report.year}"

        body_text = report.to_markdown()
        body_html = report.to_email_html()

        return self.send_email(to, subject, body_text, body_html)

    # ===========================================
    # ALERTES
    # ===========================================

    def send_inactivity_alert(
        self,
        to: str,
        profile_name: str,
        days_inactive: int,
        last_post_date: Optional[datetime],
    ) -> bool:
        """
        Envoie une alerte d'inactivité pour un profil.

        Args:
            to: Email du responsable
            profile_name: Nom du profil concerné
            days_inactive: Nombre de jours d'inactivité
            last_post_date: Date du dernier post
        """
        is_critical = days_inactive > 14

        subject_prefix = "URGENT - " if is_critical else ""
        subject = f"[FesseBook] {subject_prefix}Alerte Inactivité - {profile_name}"

        last_post_str = (
            last_post_date.strftime("%d/%m/%Y") if last_post_date else "Jamais"
        )

        body_text = f"""{"⚠️ ALERTE CRITIQUE" if is_critical else "Attention"}

Le profil "{profile_name}" est inactif depuis {days_inactive} jours.

Dernier post: {last_post_str}

Actions recommandées:
1. Vérifier la situation avec le client
2. Planifier du nouveau contenu
3. Relancer le calendrier éditorial

Merci de traiter cette alerte rapidement.

Cordialement,
L'équipe FesseBook
"""

        alert_color = "#dc3545" if is_critical else "#ffc107"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: {alert_color}; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">{"ALERTE CRITIQUE" if is_critical else "Alerte Inactivité"}</h1>
                <p style="margin: 5px 0 0 0;">{profile_name}</p>
            </div>

            <div style="padding: 20px;">
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 8px;">
                    <p style="margin: 0; font-size: 18px;">
                        <strong>{days_inactive} jours</strong> sans publication
                    </p>
                    <p style="margin: 10px 0 0 0; color: #721c24;">
                        Dernier post: {last_post_str}
                    </p>
                </div>

                <div style="margin-top: 20px;">
                    <p style="font-weight: bold;">Actions recommandées:</p>
                    <ol>
                        <li>Vérifier la situation avec le client</li>
                        <li>Planifier du nouveau contenu</li>
                        <li>Relancer le calendrier éditorial</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(to, subject, body_text, body_html)

    def send_overdue_posts_alert(
        self,
        to: str,
        overdue_posts: list[Post],
    ) -> bool:
        """
        Envoie une alerte pour les posts en retard.

        Args:
            to: Email du destinataire
            overdue_posts: Liste des posts en retard
        """
        subject = f"[FesseBook] {len(overdue_posts)} posts en retard nécessitent attention"

        body_text = f"""Attention,

{len(overdue_posts)} posts sont actuellement en retard de publication.

"""
        for post in overdue_posts:
            days_late = (datetime.now() - post.scheduled_date).days
            body_text += f"""
- {post.profile_name}: prévu le {post.scheduled_date.strftime('%d/%m')} ({days_late} jours de retard)
  "{post.content[:100]}..."
"""

        body_text += """

Merci de traiter ces publications rapidement.

Cordialement,
L'équipe FesseBook
"""

        return self.send_email(to, subject, body_text, None)
