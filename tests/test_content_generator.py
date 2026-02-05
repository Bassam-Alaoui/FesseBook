"""Tests pour le générateur de contenu."""

from datetime import datetime

import pytest

from fessebook.models.profile import ClientProfile, ContentType, PublicationFrequency
from fessebook.models.post import PostStatus
from fessebook.services.content_generator import ContentGenerator, ContentAnalyzer


class TestContentGenerator:
    """Tests pour le ContentGenerator."""

    @pytest.fixture
    def generator(self):
        """Fixture pour le générateur."""
        return ContentGenerator()

    @pytest.fixture
    def sample_profile(self):
        """Fixture pour un profil de test."""
        return ClientProfile(
            id="test-123",
            notion_page_id="notion-123",
            client_name="Test Client",
            facebook_profile_url="https://facebook.com/testclient",
            responsible_person="John Doe",
            responsible_email="john@example.com",
            content_type=ContentType.PROFESSIONAL,
            publication_frequency=PublicationFrequency.TWO_PER_WEEK,
            preferred_posting_days=["mardi", "jeudi"],
            preferred_posting_time="10:00",
            topics_of_interest=["marketing", "digital"],
            hashtags=["marketing", "business"],
        )

    def test_generate_single_post(self, generator, sample_profile):
        """Test de génération d'un seul post."""
        post = generator.generate_single_post(
            profile=sample_profile,
            scheduled_date=datetime(2024, 3, 5, 10, 0),
        )

        assert post.profile_id == sample_profile.id
        assert post.profile_name == sample_profile.client_name
        assert post.status == PostStatus.TO_VALIDATE
        assert len(post.content) > 0
        assert post.content_objective != ""

    def test_generate_posts_for_profile(self, generator, sample_profile):
        """Test de génération de plusieurs posts."""
        posts = generator.generate_posts_for_profile(
            profile=sample_profile,
            num_posts=3,
            start_date=datetime(2024, 3, 4),
        )

        assert len(posts) == 3
        # Vérifier que les dates sont sur les jours préférés (mardi, jeudi)
        for post in posts:
            assert post.scheduled_date.weekday() in [1, 3]  # mardi=1, jeudi=3

    def test_generate_week_content(self, generator, sample_profile):
        """Test de génération de contenu pour une semaine."""
        posts = generator.generate_week_content(
            profile=sample_profile,
            week_number=10,
            year=2024,
        )

        # 2 posts par semaine selon la fréquence
        assert len(posts) == 2

    def test_content_type_affects_template(self, generator):
        """Test que le type de contenu affecte le template."""
        professional_profile = ClientProfile(
            id="pro-123",
            notion_page_id="notion-123",
            client_name="Professional",
            facebook_profile_url="https://facebook.com/pro",
            responsible_person="Test",
            responsible_email="test@example.com",
            content_type=ContentType.PROFESSIONAL,
        )

        engagement_profile = ClientProfile(
            id="eng-123",
            notion_page_id="notion-123",
            client_name="Engagement",
            facebook_profile_url="https://facebook.com/eng",
            responsible_person="Test",
            responsible_email="test@example.com",
            content_type=ContentType.ENGAGEMENT,
        )

        pro_post = generator.generate_single_post(
            professional_profile, datetime.now()
        )
        eng_post = generator.generate_single_post(
            engagement_profile, datetime.now()
        )

        # Les objectifs devraient être différents
        assert pro_post.content_objective != eng_post.content_objective


class TestContentAnalyzer:
    """Tests pour le ContentAnalyzer."""

    def test_analyze_good_post(self):
        """Test d'analyse d'un bon post."""
        from fessebook.models.post import Post, PostMedia

        post = Post(
            id="post-123",
            notion_page_id="notion-123",
            profile_id="profile-123",
            profile_name="Test",
            scheduled_date=datetime.now(),
            content="Voici un post de longueur idéale avec une question engageante. Qu'en pensez-vous ? Partagez votre avis en commentaire !",
        )

        analysis = ContentAnalyzer.analyze_post_quality(post)

        assert analysis["length_score"] >= 75
        assert analysis["has_cta"] is True
        assert analysis["has_question"] is True
        assert analysis["overall_score"] >= 70

    def test_analyze_poor_post(self):
        """Test d'analyse d'un post à améliorer."""
        from fessebook.models.post import Post, PostMedia

        post = Post(
            id="post-123",
            notion_page_id="notion-123",
            profile_id="profile-123",
            profile_name="Test",
            scheduled_date=datetime.now(),
            content="Court.",
        )

        analysis = ContentAnalyzer.analyze_post_quality(post)

        assert analysis["length_score"] < 100
        assert analysis["has_cta"] is False
        assert analysis["has_question"] is False
        assert len(analysis["recommendations"]) > 0
