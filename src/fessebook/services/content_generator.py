"""Générateur de contenu pour les posts Facebook."""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fessebook.config import settings
from fessebook.models.profile import ClientProfile, ContentType
from fessebook.models.post import Post, PostMedia, PostStatus, MediaType

logger = logging.getLogger(__name__)


class ContentGenerator:
    """
    Générateur de contenu adapté aux profils clients.

    Génère des posts personnalisés selon:
    - Le type de contenu du profil
    - Le ton défini
    - Les thématiques d'intérêt
    - L'historique de performance
    """

    # Templates de posts par type de contenu
    TEMPLATES = {
        ContentType.PROFESSIONAL: [
            {
                "template": "Dans mon secteur, j'observe que {observation}. Qu'en pensez-vous ? {cta}",
                "media_suggestion": "Image professionnelle ou infographie",
                "objective": "Positionnement expert",
            },
            {
                "template": "Retour d'expérience : {experience}. La leçon que j'en tire : {lesson}. {cta}",
                "media_suggestion": "Photo contextuelle ou citation visuelle",
                "objective": "Partage d'expertise",
            },
            {
                "template": "Une question que l'on me pose souvent : {question}\n\nMa réponse : {answer} {cta}",
                "media_suggestion": "Visuel FAQ ou portrait",
                "objective": "FAQ et engagement",
            },
            {
                "template": "3 conseils pour {topic} :\n\n1. {tip1}\n2. {tip2}\n3. {tip3}\n\n{cta}",
                "media_suggestion": "Carrousel ou liste visuelle",
                "objective": "Valeur ajoutée et partage",
            },
        ],
        ContentType.PERSONAL_BRANDING: [
            {
                "template": "Ce que j'ai appris cette semaine : {learning}. {reflection} {cta}",
                "media_suggestion": "Photo personnelle authentique",
                "objective": "Authenticité et connexion",
            },
            {
                "template": "Mon parcours n'a pas toujours été simple. {story}. Aujourd'hui, {today}. {cta}",
                "media_suggestion": "Photo avant/après ou de parcours",
                "objective": "Storytelling inspirant",
            },
            {
                "template": "Pourquoi je fais ce que je fais ? {why}. {mission} {cta}",
                "media_suggestion": "Photo en action ou portrait",
                "objective": "Partage de valeurs",
            },
        ],
        ContentType.LIFESTYLE: [
            {
                "template": "{moment_description}. Ces petits moments qui font la différence. {cta}",
                "media_suggestion": "Photo de moment de vie",
                "objective": "Connexion émotionnelle",
            },
            {
                "template": "Mon rituel du {day} : {ritual}. Et vous, quel est le vôtre ? {cta}",
                "media_suggestion": "Photo du rituel",
                "objective": "Engagement communautaire",
            },
        ],
        ContentType.EDUCATIONAL: [
            {
                "template": "Le saviez-vous ? {fact}\n\n{explanation} {cta}",
                "media_suggestion": "Infographie ou visuel explicatif",
                "objective": "Éducation et valeur",
            },
            {
                "template": "Tutoriel rapide : Comment {how_to} en {steps} étapes\n\n{step_details}\n\n{cta}",
                "media_suggestion": "Tutoriel visuel ou carrousel",
                "objective": "Utilité et partage",
            },
        ],
        ContentType.PROMOTIONAL: [
            {
                "template": "Nouveauté ! {announcement}. {details}\n\n{cta}",
                "media_suggestion": "Visuel produit ou service professionnel",
                "objective": "Annonce et conversion",
            },
            {
                "template": "Témoignage client : \"{testimonial}\"\n\nMerci {client_name} pour cette confiance ! {cta}",
                "media_suggestion": "Photo avec le client (si autorisé) ou visuel témoignage",
                "objective": "Preuve sociale",
            },
        ],
        ContentType.ENGAGEMENT: [
            {
                "template": "Question du jour : {question} {cta}",
                "media_suggestion": "Visuel avec la question",
                "objective": "Générer des commentaires",
            },
            {
                "template": "{statement} - D'accord ou pas d'accord ? Dites-moi pourquoi ! {cta}",
                "media_suggestion": "Visuel débat ou sondage",
                "objective": "Créer le débat",
            },
            {
                "template": "Si vous deviez choisir entre {option1} et {option2}, que choisiriez-vous ? {cta}",
                "media_suggestion": "Visuel comparatif",
                "objective": "Sondage et engagement",
            },
        ],
    }

    # Call-to-actions variés
    CTAS = {
        "engagement": [
            "Partagez votre avis en commentaire !",
            "Et vous, qu'en pensez-vous ?",
            "Dites-moi en commentaire !",
            "Votre expérience m'intéresse, partagez-la !",
            "N'hésitez pas à commenter et partager si ça vous parle !",
        ],
        "share": [
            "Si ce post vous a plu, partagez-le !",
            "Taguez quelqu'un qui devrait voir ça !",
            "Partagez à quelqu'un qui en a besoin !",
        ],
        "contact": [
            "Envoyez-moi un message pour en discuter !",
            "Contactez-moi pour en savoir plus !",
            "Mes DM sont ouverts si vous avez des questions !",
        ],
        "subtle": [
            "",
            "Bonne journée à tous !",
            "Belle semaine !",
        ],
    }

    def __init__(self):
        """Initialise le générateur de contenu."""
        self.has_ai = settings.has_ai_content_generation

    def generate_posts_for_profile(
        self,
        profile: ClientProfile,
        num_posts: int,
        start_date: datetime,
    ) -> list[Post]:
        """
        Génère plusieurs posts pour un profil.

        Args:
            profile: Le profil client
            num_posts: Nombre de posts à générer
            start_date: Date de début pour la planification

        Returns:
            Liste de posts générés
        """
        posts = []
        current_date = start_date

        # Déterminer les jours de publication préférés
        posting_days = profile.preferred_posting_days or ["mardi", "jeudi"]
        day_mapping = {
            "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
            "vendredi": 4, "samedi": 5, "dimanche": 6
        }
        preferred_weekdays = [day_mapping.get(d.lower(), 1) for d in posting_days]

        for i in range(num_posts):
            # Trouver le prochain jour de publication
            while current_date.weekday() not in preferred_weekdays:
                current_date += timedelta(days=1)

            post = self.generate_single_post(
                profile=profile,
                scheduled_date=current_date,
                variation_index=i,
            )
            posts.append(post)

            # Avancer au prochain jour
            current_date += timedelta(days=1)

        return posts

    def generate_single_post(
        self,
        profile: ClientProfile,
        scheduled_date: datetime,
        variation_index: int = 0,
    ) -> Post:
        """
        Génère un seul post pour un profil.

        Args:
            profile: Le profil client
            scheduled_date: Date de publication prévue
            variation_index: Index pour varier les templates

        Returns:
            Un post généré
        """
        # Sélectionner le type de contenu
        content_type = profile.content_type
        if content_type == ContentType.MIXED:
            content_type = random.choice([
                ContentType.PROFESSIONAL,
                ContentType.PERSONAL_BRANDING,
                ContentType.ENGAGEMENT,
            ])

        # Obtenir les templates disponibles
        templates = self.TEMPLATES.get(content_type, self.TEMPLATES[ContentType.ENGAGEMENT])

        # Sélectionner un template en variant
        template_data = templates[variation_index % len(templates)]

        # Générer le contenu
        content = self._fill_template(
            template=template_data["template"],
            profile=profile,
            content_type=content_type,
        )

        # Créer le post
        return Post(
            id=str(uuid4()),
            notion_page_id="",  # Sera rempli lors de la création dans Notion
            profile_id=profile.id,
            profile_name=profile.client_name,
            scheduled_date=scheduled_date,
            scheduled_time=profile.preferred_posting_time,
            content=content,
            content_objective=template_data["objective"],
            media=PostMedia(
                type=MediaType.IMAGE,
                suggestion=template_data["media_suggestion"],
            ),
            status=PostStatus.TO_VALIDATE,
            expected_engagement=self._estimate_engagement(content_type),
            created_by="content_generator",
        )

    def _fill_template(
        self,
        template: str,
        profile: ClientProfile,
        content_type: ContentType,
    ) -> str:
        """
        Remplit un template avec des placeholders adaptés au profil.

        Note: En production, cette méthode pourrait utiliser une IA
        pour générer du contenu plus personnalisé.
        """
        # Sélectionner un CTA approprié
        cta_type = "engagement" if content_type == ContentType.ENGAGEMENT else "subtle"
        cta = random.choice(self.CTAS.get(cta_type, self.CTAS["subtle"]))

        # Créer un dictionnaire de placeholders par défaut
        # Ces valeurs seraient idéalement générées par une IA ou définies manuellement
        topics = profile.topics_of_interest or ["mon domaine", "mon activité"]
        topic = random.choice(topics) if topics else "mon domaine"

        placeholders = {
            "cta": cta,
            "topic": topic,
            "observation": f"[À personnaliser: observation sur {topic}]",
            "experience": f"[À personnaliser: expérience récente liée à {topic}]",
            "lesson": "[À personnaliser: leçon tirée]",
            "question": f"[À personnaliser: question fréquente sur {topic}]",
            "answer": "[À personnaliser: votre réponse experte]",
            "tip1": "[Conseil 1]",
            "tip2": "[Conseil 2]",
            "tip3": "[Conseil 3]",
            "learning": "[Ce que vous avez appris cette semaine]",
            "reflection": "[Votre réflexion personnelle]",
            "story": "[Élément de votre parcours]",
            "today": "[Votre situation actuelle]",
            "why": "[Votre motivation profonde]",
            "mission": "[Votre mission]",
            "moment_description": "[Description d'un moment de vie]",
            "day": random.choice(["lundi", "mardi", "mercredi", "jeudi", "vendredi"]),
            "ritual": "[Votre rituel]",
            "fact": f"[Fait intéressant sur {topic}]",
            "explanation": "[Explication détaillée]",
            "how_to": f"[réaliser quelque chose en lien avec {topic}]",
            "steps": "3",
            "step_details": "1. [Étape 1]\n2. [Étape 2]\n3. [Étape 3]",
            "announcement": "[Votre nouveauté]",
            "details": "[Détails de l'offre]",
            "testimonial": "[Témoignage client]",
            "client_name": "[Prénom du client]",
            "statement": f"[Affirmation sur {topic}]",
            "option1": "[Option A]",
            "option2": "[Option B]",
        }

        # Ajouter les hashtags du profil si présents
        if profile.hashtags:
            hashtags_str = " ".join(f"#{h}" for h in profile.hashtags[:3])
            placeholders["cta"] = f"{cta}\n\n{hashtags_str}"

        # Remplir le template
        try:
            content = template.format(**placeholders)
        except KeyError as e:
            logger.warning(f"Placeholder manquant: {e}")
            content = template

        return content

    def _estimate_engagement(self, content_type: ContentType) -> str:
        """Estime l'engagement attendu selon le type de contenu."""
        estimates = {
            ContentType.PROFESSIONAL: "5-15 interactions",
            ContentType.PERSONAL_BRANDING: "10-25 interactions",
            ContentType.LIFESTYLE: "15-30 interactions",
            ContentType.EDUCATIONAL: "10-20 interactions + partages",
            ContentType.PROMOTIONAL: "5-10 interactions",
            ContentType.ENGAGEMENT: "20-40+ commentaires",
            ContentType.MIXED: "10-20 interactions",
        }
        return estimates.get(content_type, "10-20 interactions")

    def generate_week_content(
        self,
        profile: ClientProfile,
        week_number: int,
        year: int,
    ) -> list[Post]:
        """
        Génère le contenu pour une semaine complète.

        Args:
            profile: Le profil client
            week_number: Numéro de la semaine
            year: Année

        Returns:
            Liste des posts pour la semaine
        """
        # Calculer la date de début de semaine
        first_day_of_year = datetime(year, 1, 1)
        start_of_week = first_day_of_year + timedelta(weeks=week_number - 1)
        start_of_week = start_of_week - timedelta(days=start_of_week.weekday())

        # Déterminer le nombre de posts selon la fréquence
        num_posts = profile.get_posts_per_week()

        return self.generate_posts_for_profile(
            profile=profile,
            num_posts=num_posts,
            start_date=start_of_week,
        )

    def improve_post_with_feedback(
        self,
        post: Post,
        feedback: str,
    ) -> Post:
        """
        Améliore un post basé sur le feedback de validation.

        Args:
            post: Le post à améliorer
            feedback: Le feedback reçu

        Returns:
            Post mis à jour avec les modifications suggérées
        """
        # En production, cette méthode utiliserait une IA pour
        # intégrer le feedback de manière intelligente
        post.modification_notes = feedback
        post.status = PostStatus.TO_VALIDATE
        post.content = f"{post.content}\n\n[MODIFICATION REQUISE: {feedback}]"

        return post


class ContentAnalyzer:
    """Analyse le contenu pour optimisation."""

    @staticmethod
    def analyze_post_quality(post: Post) -> dict:
        """
        Analyse la qualité d'un post.

        Returns:
            Dictionnaire avec les scores et recommandations
        """
        content = post.content
        analysis = {
            "length_score": 0,
            "has_cta": False,
            "has_question": False,
            "has_emoji": False,
            "recommendations": [],
        }

        # Analyse de la longueur (optimal: 100-300 caractères pour Facebook)
        length = len(content)
        if 100 <= length <= 300:
            analysis["length_score"] = 100
        elif 50 <= length < 100 or 300 < length <= 500:
            analysis["length_score"] = 75
        else:
            analysis["length_score"] = 50
            analysis["recommendations"].append(
                "Ajuster la longueur du post (idéal: 100-300 caractères)"
            )

        # Présence d'un CTA
        cta_keywords = ["commentaire", "partagez", "dites", "qu'en pensez", "?"]
        analysis["has_cta"] = any(kw in content.lower() for kw in cta_keywords)
        if not analysis["has_cta"]:
            analysis["recommendations"].append(
                "Ajouter un appel à l'action pour augmenter l'engagement"
            )

        # Présence d'une question
        analysis["has_question"] = "?" in content
        if not analysis["has_question"]:
            analysis["recommendations"].append(
                "Inclure une question pour encourager les réponses"
            )

        # Score global
        analysis["overall_score"] = (
            analysis["length_score"] * 0.3
            + (100 if analysis["has_cta"] else 0) * 0.4
            + (100 if analysis["has_question"] else 0) * 0.3
        )

        return analysis
