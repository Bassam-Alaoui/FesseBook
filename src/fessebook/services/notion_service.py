"""Service d'intégration avec Notion - Source de vérité centrale."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from notion_client import Client
from notion_client.errors import APIResponseError

from fessebook.config import settings
from fessebook.models.profile import (
    ClientProfile,
    ContentType,
    ProfileStatus,
    PublicationFrequency,
)
from fessebook.models.post import Post, PostMedia, PostStatus, MediaType
from fessebook.models.performance import Performance, PerformanceMetrics, EngagementLevel

logger = logging.getLogger(__name__)


class NotionService:
    """
    Service de gestion des données Notion.

    Notion est la source de vérité principale pour:
    - Les profils clients
    - Le calendrier éditorial
    - Les performances
    """

    def __init__(self, token: Optional[str] = None):
        """Initialise le client Notion."""
        self.token = token or settings.notion_token
        self.client = Client(auth=self.token)

        self.db_profiles = settings.notion_db_profiles
        self.db_calendar = settings.notion_db_calendar
        self.db_performance = settings.notion_db_performance

    # ===========================================
    # PROFILS CLIENTS
    # ===========================================

    def get_all_profiles(self) -> list[ClientProfile]:
        """Récupère tous les profils clients."""
        try:
            response = self.client.databases.query(database_id=self.db_profiles)
            return [self._parse_profile(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des profils: {e}")
            raise

    def get_active_profiles(self) -> list[ClientProfile]:
        """Récupère uniquement les profils actifs."""
        try:
            response = self.client.databases.query(
                database_id=self.db_profiles,
                filter={
                    "property": "Statut",
                    "select": {"equals": "actif"},
                },
            )
            return [self._parse_profile(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des profils actifs: {e}")
            raise

    def get_profiles_needing_content(self) -> list[ClientProfile]:
        """Récupère les profils qui ont besoin de nouveau contenu."""
        profiles = self.get_active_profiles()
        return [p for p in profiles if p.needs_content()]

    def get_profiles_at_risk(self, days_threshold: int = 7) -> list[ClientProfile]:
        """Récupère les profils à risque d'inactivité."""
        profiles = self.get_active_profiles()
        return [p for p in profiles if p.is_overdue(days_threshold)]

    def get_profile_by_id(self, profile_id: str) -> Optional[ClientProfile]:
        """Récupère un profil par son ID."""
        try:
            page = self.client.pages.retrieve(page_id=profile_id)
            return self._parse_profile(page)
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération du profil {profile_id}: {e}")
            return None

    def update_profile_last_publication(
        self, profile_id: str, publication_date: datetime
    ) -> bool:
        """Met à jour la date de dernière publication d'un profil."""
        try:
            self.client.pages.update(
                page_id=profile_id,
                properties={
                    "Dernière publication": {
                        "date": {"start": publication_date.isoformat()}
                    }
                },
            )
            return True
        except APIResponseError as e:
            logger.error(f"Erreur lors de la mise à jour du profil {profile_id}: {e}")
            return False

    def _parse_profile(self, page: dict) -> ClientProfile:
        """Parse une page Notion en ClientProfile."""
        props = page.get("properties", {})

        # Extraction des propriétés avec gestion des valeurs manquantes
        def get_title(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            title_list = prop.get("title", [])
            return title_list[0].get("plain_text", "") if title_list else ""

        def get_rich_text(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            text_list = prop.get("rich_text", [])
            return text_list[0].get("plain_text", "") if text_list else ""

        def get_url(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            return prop.get("url", "")

        def get_select(prop_name: str) -> Optional[str]:
            prop = props.get(prop_name, {})
            select = prop.get("select")
            return select.get("name") if select else None

        def get_multi_select(prop_name: str) -> list[str]:
            prop = props.get(prop_name, {})
            return [item.get("name", "") for item in prop.get("multi_select", [])]

        def get_email(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            return prop.get("email", "")

        def get_date(prop_name: str) -> Optional[datetime]:
            prop = props.get(prop_name, {})
            date_obj = prop.get("date")
            if date_obj and date_obj.get("start"):
                return datetime.fromisoformat(date_obj["start"].replace("Z", "+00:00"))
            return None

        # Calcul des jours depuis la dernière publication
        last_pub = get_date("Dernière publication")
        days_since = None
        if last_pub:
            days_since = (datetime.now(last_pub.tzinfo) - last_pub).days

        # Mapping des statuts
        status_map = {
            "actif": ProfileStatus.ACTIVE,
            "inactif": ProfileStatus.INACTIVE,
            "en_pause": ProfileStatus.PAUSED,
            "en_configuration": ProfileStatus.PENDING_SETUP,
        }

        # Mapping des types de contenu
        content_type_map = {
            "professionnel": ContentType.PROFESSIONAL,
            "personal_branding": ContentType.PERSONAL_BRANDING,
            "lifestyle": ContentType.LIFESTYLE,
            "educatif": ContentType.EDUCATIONAL,
            "promotionnel": ContentType.PROMOTIONAL,
            "engagement": ContentType.ENGAGEMENT,
            "mixte": ContentType.MIXED,
        }

        # Mapping des fréquences
        frequency_map = {
            "quotidien": PublicationFrequency.DAILY,
            "3_par_semaine": PublicationFrequency.THREE_PER_WEEK,
            "2_par_semaine": PublicationFrequency.TWO_PER_WEEK,
            "hebdomadaire": PublicationFrequency.WEEKLY,
            "bi_mensuel": PublicationFrequency.BIWEEKLY,
        }

        return ClientProfile(
            id=page["id"],
            notion_page_id=page["id"],
            client_name=get_title("Nom du client") or "Sans nom",
            facebook_profile_url=get_url("Profil Facebook") or "https://facebook.com",
            responsible_person=get_rich_text("Responsable"),
            responsible_email=get_email("Email responsable") or get_rich_text("Email responsable"),
            content_type=content_type_map.get(
                get_select("Type de contenu") or "", ContentType.MIXED
            ),
            publication_frequency=frequency_map.get(
                get_select("Fréquence") or "", PublicationFrequency.TWO_PER_WEEK
            ),
            preferred_posting_days=get_multi_select("Jours de publication") or ["mardi", "jeudi"],
            preferred_posting_time=get_rich_text("Heure de publication") or "10:00",
            tone_description=get_rich_text("Description du ton"),
            topics_of_interest=get_multi_select("Thématiques"),
            hashtags=get_multi_select("Hashtags"),
            avoid_topics=get_multi_select("Sujets à éviter"),
            status=status_map.get(get_select("Statut") or "", ProfileStatus.ACTIVE),
            last_publication_date=last_pub,
            days_since_last_post=days_since,
            notes=get_rich_text("Notes"),
        )

    # ===========================================
    # CALENDRIER ÉDITORIAL
    # ===========================================

    def get_all_posts(self) -> list[Post]:
        """Récupère tous les posts du calendrier."""
        try:
            response = self.client.databases.query(database_id=self.db_calendar)
            return [self._parse_post(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des posts: {e}")
            raise

    def get_posts_by_status(self, status: PostStatus) -> list[Post]:
        """Récupère les posts par statut."""
        try:
            response = self.client.databases.query(
                database_id=self.db_calendar,
                filter={
                    "property": "Statut",
                    "select": {"equals": status.value},
                },
            )
            return [self._parse_post(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des posts: {e}")
            raise

    def get_posts_to_validate(self) -> list[Post]:
        """Récupère les posts en attente de validation."""
        return self.get_posts_by_status(PostStatus.TO_VALIDATE)

    def get_posts_to_publish_today(self) -> list[Post]:
        """Récupère les posts à publier aujourd'hui."""
        today = datetime.now().date()
        posts = self.get_posts_by_status(PostStatus.VALIDATED)
        posts += self.get_posts_by_status(PostStatus.TO_PUBLISH)

        return [p for p in posts if p.scheduled_date.date() == today]

    def get_posts_for_profile(
        self, profile_id: str, start_date: Optional[datetime] = None
    ) -> list[Post]:
        """Récupère les posts d'un profil."""
        filters = [{"property": "Profil", "relation": {"contains": profile_id}}]

        if start_date:
            filters.append(
                {
                    "property": "Date de publication",
                    "date": {"on_or_after": start_date.isoformat()},
                }
            )

        try:
            response = self.client.databases.query(
                database_id=self.db_calendar,
                filter={"and": filters} if len(filters) > 1 else filters[0],
            )
            return [self._parse_post(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des posts du profil: {e}")
            raise

    def get_overdue_posts(self) -> list[Post]:
        """Récupère les posts en retard."""
        posts = self.get_all_posts()
        return [p for p in posts if p.is_overdue() and p.status != PostStatus.PUBLISHED]

    def get_posts_for_week(self, week_number: int, year: int) -> list[Post]:
        """Récupère les posts planifiés pour une semaine donnée."""
        # Calculer les dates de début et fin de semaine
        first_day_of_year = datetime(year, 1, 1)
        start_of_week = first_day_of_year + timedelta(weeks=week_number - 1)
        # Ajuster au lundi
        start_of_week = start_of_week - timedelta(days=start_of_week.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        try:
            response = self.client.databases.query(
                database_id=self.db_calendar,
                filter={
                    "and": [
                        {
                            "property": "Date de publication",
                            "date": {"on_or_after": start_of_week.isoformat()},
                        },
                        {
                            "property": "Date de publication",
                            "date": {"on_or_before": end_of_week.isoformat()},
                        },
                    ]
                },
            )
            return [self._parse_post(page) for page in response.get("results", [])]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des posts de la semaine: {e}")
            raise

    def create_post(self, post: Post) -> str:
        """Crée un nouveau post dans le calendrier éditorial."""
        try:
            response = self.client.pages.create(
                parent={"database_id": self.db_calendar},
                properties=self._post_to_notion_properties(post),
            )
            return response["id"]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la création du post: {e}")
            raise

    def update_post_status(self, post_id: str, status: PostStatus) -> bool:
        """Met à jour le statut d'un post."""
        try:
            self.client.pages.update(
                page_id=post_id,
                properties={"Statut": {"select": {"name": status.value}}},
            )
            return True
        except APIResponseError as e:
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")
            return False

    def mark_post_published(
        self, post_id: str, published_at: datetime, confirmed_by: str
    ) -> bool:
        """Marque un post comme publié."""
        try:
            self.client.pages.update(
                page_id=post_id,
                properties={
                    "Statut": {"select": {"name": PostStatus.PUBLISHED.value}},
                    "Date publication effective": {
                        "date": {"start": published_at.isoformat()}
                    },
                    "Confirmé par": {"rich_text": [{"text": {"content": confirmed_by}}]},
                },
            )
            return True
        except APIResponseError as e:
            logger.error(f"Erreur lors du marquage comme publié: {e}")
            return False

    def _parse_post(self, page: dict) -> Post:
        """Parse une page Notion en Post."""
        props = page.get("properties", {})

        def get_title(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            title_list = prop.get("title", [])
            return title_list[0].get("plain_text", "") if title_list else ""

        def get_rich_text(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            text_list = prop.get("rich_text", [])
            return text_list[0].get("plain_text", "") if text_list else ""

        def get_select(prop_name: str) -> Optional[str]:
            prop = props.get(prop_name, {})
            select = prop.get("select")
            return select.get("name") if select else None

        def get_date(prop_name: str) -> Optional[datetime]:
            prop = props.get(prop_name, {})
            date_obj = prop.get("date")
            if date_obj and date_obj.get("start"):
                return datetime.fromisoformat(date_obj["start"].replace("Z", "+00:00"))
            return None

        def get_relation(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            relations = prop.get("relation", [])
            return relations[0].get("id", "") if relations else ""

        def get_url(prop_name: str) -> Optional[str]:
            prop = props.get(prop_name, {})
            return prop.get("url")

        # Mapping des statuts
        status_map = {
            "a_generer": PostStatus.TO_GENERATE,
            "a_valider": PostStatus.TO_VALIDATE,
            "valide": PostStatus.VALIDATED,
            "a_publier": PostStatus.TO_PUBLISH,
            "publie": PostStatus.PUBLISHED,
            "en_retard": PostStatus.OVERDUE,
            "rejete": PostStatus.REJECTED,
        }

        # Mapping des types de média
        media_type_map = {
            "image": MediaType.IMAGE,
            "video": MediaType.VIDEO,
            "carousel": MediaType.CAROUSEL,
            "lien": MediaType.LINK,
        }

        media = PostMedia(
            type=media_type_map.get(get_select("Type média") or "", MediaType.NONE),
            url=get_url("URL média"),
            suggestion=get_rich_text("Suggestion média"),
        )

        scheduled = get_date("Date de publication")
        if not scheduled:
            scheduled = datetime.now()

        return Post(
            id=page["id"],
            notion_page_id=page["id"],
            profile_id=get_relation("Profil"),
            profile_name=get_rich_text("Nom profil") or "N/A",
            scheduled_date=scheduled,
            scheduled_time=get_rich_text("Heure") or "10:00",
            content=get_rich_text("Texte du post") or get_title("Titre"),
            content_objective=get_rich_text("Objectif"),
            call_to_action=get_rich_text("Call to action"),
            media=media,
            status=status_map.get(get_select("Statut") or "", PostStatus.TO_GENERATE),
            validated_by=get_rich_text("Validé par"),
            rejection_reason=get_rich_text("Raison rejet"),
            expected_engagement=get_rich_text("Engagement attendu"),
        )

    def _post_to_notion_properties(self, post: Post) -> dict:
        """Convertit un Post en propriétés Notion."""
        properties = {
            "Texte du post": {
                "rich_text": [{"text": {"content": post.content[:2000]}}]
            },
            "Date de publication": {"date": {"start": post.scheduled_date.isoformat()}},
            "Heure": {"rich_text": [{"text": {"content": post.scheduled_time}}]},
            "Statut": {"select": {"name": post.status.value}},
            "Objectif": {
                "rich_text": [{"text": {"content": post.content_objective}}]
            },
        }

        if post.profile_id:
            properties["Profil"] = {"relation": [{"id": post.profile_id}]}

        if post.media.suggestion:
            properties["Suggestion média"] = {
                "rich_text": [{"text": {"content": post.media.suggestion}}]
            }

        if post.media.type != MediaType.NONE:
            properties["Type média"] = {"select": {"name": post.media.type.value}}

        return properties

    # ===========================================
    # PERFORMANCE
    # ===========================================

    def get_performance_for_post(self, post_id: str) -> Optional[Performance]:
        """Récupère les données de performance d'un post."""
        try:
            response = self.client.databases.query(
                database_id=self.db_performance,
                filter={"property": "Post", "relation": {"contains": post_id}},
            )
            results = response.get("results", [])
            return self._parse_performance(results[0]) if results else None
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération de la performance: {e}")
            return None

    def get_performances_for_profile(
        self, profile_id: str, start_date: Optional[datetime] = None
    ) -> list[Performance]:
        """Récupère les performances d'un profil."""
        filters = [{"property": "Profil", "relation": {"contains": profile_id}}]

        if start_date:
            filters.append(
                {
                    "property": "Date publication",
                    "date": {"on_or_after": start_date.isoformat()},
                }
            )

        try:
            response = self.client.databases.query(
                database_id=self.db_performance,
                filter={"and": filters} if len(filters) > 1 else filters[0],
            )
            return [
                self._parse_performance(page) for page in response.get("results", [])
            ]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la récupération des performances: {e}")
            raise

    def create_performance_entry(self, performance: Performance) -> str:
        """Crée une nouvelle entrée de performance."""
        try:
            response = self.client.pages.create(
                parent={"database_id": self.db_performance},
                properties=self._performance_to_notion_properties(performance),
            )
            return response["id"]
        except APIResponseError as e:
            logger.error(f"Erreur lors de la création de la performance: {e}")
            raise

    def update_performance_metrics(
        self, performance_id: str, metrics: PerformanceMetrics
    ) -> bool:
        """Met à jour les métriques d'une entrée de performance."""
        try:
            self.client.pages.update(
                page_id=performance_id,
                properties={
                    "Likes": {"number": metrics.likes},
                    "Commentaires": {"number": metrics.comments},
                    "Partages": {"number": metrics.shares},
                    "Messages reçus": {"number": metrics.messages_received},
                    "Date collecte": {"date": {"start": datetime.now().isoformat()}},
                },
            )
            return True
        except APIResponseError as e:
            logger.error(f"Erreur lors de la mise à jour des métriques: {e}")
            return False

    def _parse_performance(self, page: dict) -> Performance:
        """Parse une page Notion en Performance."""
        props = page.get("properties", {})

        def get_number(prop_name: str) -> int:
            prop = props.get(prop_name, {})
            return int(prop.get("number", 0) or 0)

        def get_rich_text(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            text_list = prop.get("rich_text", [])
            return text_list[0].get("plain_text", "") if text_list else ""

        def get_select(prop_name: str) -> Optional[str]:
            prop = props.get(prop_name, {})
            select = prop.get("select")
            return select.get("name") if select else None

        def get_date(prop_name: str) -> Optional[datetime]:
            prop = props.get(prop_name, {})
            date_obj = prop.get("date")
            if date_obj and date_obj.get("start"):
                return datetime.fromisoformat(date_obj["start"].replace("Z", "+00:00"))
            return None

        def get_relation(prop_name: str) -> str:
            prop = props.get(prop_name, {})
            relations = prop.get("relation", [])
            return relations[0].get("id", "") if relations else ""

        def get_multi_select(prop_name: str) -> list[str]:
            prop = props.get(prop_name, {})
            return [item.get("name", "") for item in prop.get("multi_select", [])]

        metrics = PerformanceMetrics(
            likes=get_number("Likes"),
            comments=get_number("Commentaires"),
            shares=get_number("Partages"),
            messages_received=get_number("Messages reçus"),
        )

        # Mapping des niveaux d'engagement
        engagement_map = {
            "excellent": EngagementLevel.EXCELLENT,
            "bon": EngagementLevel.GOOD,
            "moyen": EngagementLevel.AVERAGE,
            "faible": EngagementLevel.LOW,
            "tres_faible": EngagementLevel.VERY_LOW,
        }

        pub_date = get_date("Date publication")
        if not pub_date:
            pub_date = datetime.now()

        return Performance(
            id=page["id"],
            notion_page_id=page["id"],
            post_id=get_relation("Post"),
            profile_id=get_relation("Profil"),
            profile_name=get_rich_text("Nom profil"),
            publication_date=pub_date,
            metrics_collected_at=get_date("Date collecte"),
            metrics=metrics,
            engagement_level=engagement_map.get(
                get_select("Niveau engagement") or "", EngagementLevel.AVERAGE
            ),
            qualitative_observations=get_rich_text("Observations"),
            notable_comments=get_multi_select("Commentaires notables"),
            sentiment=get_select("Sentiment") or "neutre",
            recommendations=get_multi_select("Recommandations"),
            reported_by=get_rich_text("Rapporté par"),
        )

    def _performance_to_notion_properties(self, performance: Performance) -> dict:
        """Convertit une Performance en propriétés Notion."""
        properties = {
            "Date publication": {
                "date": {"start": performance.publication_date.isoformat()}
            },
            "Likes": {"number": performance.metrics.likes},
            "Commentaires": {"number": performance.metrics.comments},
            "Partages": {"number": performance.metrics.shares},
            "Messages reçus": {"number": performance.metrics.messages_received},
            "Niveau engagement": {
                "select": {"name": performance.engagement_level.value}
            },
            "Observations": {
                "rich_text": [
                    {"text": {"content": performance.qualitative_observations[:2000]}}
                ]
            },
            "Sentiment": {"select": {"name": performance.sentiment}},
        }

        if performance.post_id:
            properties["Post"] = {"relation": [{"id": performance.post_id}]}
        if performance.profile_id:
            properties["Profil"] = {"relation": [{"id": performance.profile_id}]}

        return properties
