"""Tests pour les modèles de données."""

from datetime import datetime, timedelta

import pytest

from fessebook.models.profile import (
    ClientProfile,
    ProfileStatus,
    ContentType,
    PublicationFrequency,
)
from fessebook.models.post import Post, PostStatus, PostMedia, MediaType
from fessebook.models.performance import Performance, PerformanceMetrics, EngagementLevel
from fessebook.models.report import WeeklyReport, ProfileReport, ActionItem, ActionPriority, ActionType


class TestClientProfile:
    """Tests pour le modèle ClientProfile."""

    def test_create_profile(self):
        """Test de création d'un profil."""
        profile = ClientProfile(
            id="test-123",
            notion_page_id="notion-123",
            client_name="Test Client",
            facebook_profile_url="https://facebook.com/testclient",
            responsible_person="John Doe",
            responsible_email="john@example.com",
        )

        assert profile.client_name == "Test Client"
        assert profile.status == ProfileStatus.ACTIVE
        assert profile.content_type == ContentType.MIXED

    def test_is_overdue(self):
        """Test de la détection de retard."""
        profile = ClientProfile(
            id="test-123",
            notion_page_id="notion-123",
            client_name="Test",
            facebook_profile_url="https://facebook.com/test",
            responsible_person="Test",
            responsible_email="test@example.com",
            days_since_last_post=10,
        )

        assert profile.is_overdue(threshold_days=7) is True
        assert profile.is_overdue(threshold_days=14) is False

    def test_needs_content(self):
        """Test de la détection du besoin de contenu."""
        active_overdue = ClientProfile(
            id="test-1",
            notion_page_id="notion-1",
            client_name="Active Overdue",
            facebook_profile_url="https://facebook.com/test1",
            responsible_person="Test",
            responsible_email="test@example.com",
            status=ProfileStatus.ACTIVE,
            days_since_last_post=10,
        )

        inactive = ClientProfile(
            id="test-2",
            notion_page_id="notion-2",
            client_name="Inactive",
            facebook_profile_url="https://facebook.com/test2",
            responsible_person="Test",
            responsible_email="test@example.com",
            status=ProfileStatus.INACTIVE,
            days_since_last_post=10,
        )

        assert active_overdue.needs_content() is True
        assert inactive.needs_content() is False

    def test_get_posts_per_week(self):
        """Test du calcul des posts par semaine."""
        profile = ClientProfile(
            id="test-123",
            notion_page_id="notion-123",
            client_name="Test",
            facebook_profile_url="https://facebook.com/test",
            responsible_person="Test",
            responsible_email="test@example.com",
            publication_frequency=PublicationFrequency.THREE_PER_WEEK,
        )

        assert profile.get_posts_per_week() == 3


class TestPost:
    """Tests pour le modèle Post."""

    def test_create_post(self):
        """Test de création d'un post."""
        post = Post(
            id="post-123",
            notion_page_id="notion-123",
            profile_id="profile-123",
            profile_name="Test Profile",
            scheduled_date=datetime.now(),
            content="Contenu de test",
        )

        assert post.content == "Contenu de test"
        assert post.status == PostStatus.TO_GENERATE

    def test_is_overdue(self):
        """Test de la détection de retard."""
        past_post = Post(
            id="post-1",
            notion_page_id="notion-1",
            profile_id="profile-1",
            profile_name="Test",
            scheduled_date=datetime.now() - timedelta(days=2),
            content="Test",
            status=PostStatus.TO_PUBLISH,
        )

        future_post = Post(
            id="post-2",
            notion_page_id="notion-2",
            profile_id="profile-2",
            profile_name="Test",
            scheduled_date=datetime.now() + timedelta(days=2),
            content="Test",
            status=PostStatus.TO_PUBLISH,
        )

        published_post = Post(
            id="post-3",
            notion_page_id="notion-3",
            profile_id="profile-3",
            profile_name="Test",
            scheduled_date=datetime.now() - timedelta(days=2),
            content="Test",
            status=PostStatus.PUBLISHED,
        )

        assert past_post.is_overdue() is True
        assert future_post.is_overdue() is False
        assert published_post.is_overdue() is False

    def test_mark_as_validated(self):
        """Test du marquage comme validé."""
        post = Post(
            id="post-123",
            notion_page_id="notion-123",
            profile_id="profile-123",
            profile_name="Test",
            scheduled_date=datetime.now(),
            content="Test",
            status=PostStatus.TO_VALIDATE,
        )

        post.mark_as_validated("validator@example.com")

        assert post.status == PostStatus.VALIDATED
        assert post.validated_by == "validator@example.com"
        assert post.validated_at is not None


class TestPerformance:
    """Tests pour le modèle Performance."""

    def test_create_performance(self):
        """Test de création d'une performance."""
        perf = Performance(
            id="perf-123",
            notion_page_id="notion-123",
            post_id="post-123",
            profile_id="profile-123",
            profile_name="Test",
            publication_date=datetime.now(),
            metrics=PerformanceMetrics(likes=10, comments=5, shares=2),
        )

        assert perf.metrics.likes == 10
        assert perf.metrics.total_engagement == 10 + 5 * 2 + 2 * 3  # 26

    def test_calculate_engagement_level(self):
        """Test du calcul du niveau d'engagement."""
        excellent = Performance(
            id="perf-1",
            notion_page_id="notion-1",
            post_id="post-1",
            profile_id="profile-1",
            profile_name="Test",
            publication_date=datetime.now(),
            metrics=PerformanceMetrics(likes=50, comments=10, shares=5),
        )

        low = Performance(
            id="perf-2",
            notion_page_id="notion-2",
            post_id="post-2",
            profile_id="profile-2",
            profile_name="Test",
            publication_date=datetime.now(),
            metrics=PerformanceMetrics(likes=2, comments=0, shares=0),
        )

        assert excellent.calculate_engagement_level() == EngagementLevel.EXCELLENT
        assert low.calculate_engagement_level() == EngagementLevel.VERY_LOW


class TestWeeklyReport:
    """Tests pour le modèle WeeklyReport."""

    def test_create_report(self):
        """Test de création d'un rapport."""
        report = WeeklyReport(
            week_number=10,
            year=2024,
            period_start=datetime(2024, 3, 4),
            period_end=datetime(2024, 3, 10),
        )

        assert report.week_number == 10
        assert report.total_profiles == 0

    def test_calculate_statistics(self):
        """Test du calcul des statistiques."""
        report = WeeklyReport(
            week_number=10,
            year=2024,
            period_start=datetime(2024, 3, 4),
            period_end=datetime(2024, 3, 10),
            profile_reports=[
                ProfileReport(
                    profile_id="1",
                    profile_name="Profile 1",
                    responsible_person="John",
                    posts_planned=5,
                    posts_published=4,
                    total_likes=20,
                    is_active=True,
                ),
                ProfileReport(
                    profile_id="2",
                    profile_name="Profile 2",
                    responsible_person="Jane",
                    posts_planned=3,
                    posts_published=3,
                    total_likes=30,
                    is_active=True,
                ),
            ],
        )

        report.calculate_statistics()

        assert report.total_profiles == 2
        assert report.active_profiles == 2
        assert report.total_posts_planned == 8
        assert report.total_posts_published == 7
        assert report.total_likes == 50

    def test_to_markdown(self):
        """Test de la génération Markdown."""
        report = WeeklyReport(
            week_number=10,
            year=2024,
            period_start=datetime(2024, 3, 4),
            period_end=datetime(2024, 3, 10),
            total_profiles=5,
            active_profiles=4,
        )

        markdown = report.to_markdown()

        assert "Semaine 10/2024" in markdown
        assert "Profils gérés" in markdown


class TestActionItem:
    """Tests pour le modèle ActionItem."""

    def test_to_markdown(self):
        """Test de la conversion en Markdown."""
        action = ActionItem(
            type=ActionType.PUBLISH_POST,
            priority=ActionPriority.URGENT,
            profile_name="Test Profile",
            description="Publication en retard",
        )

        markdown = action.to_markdown()

        assert "publier_post" in markdown
        assert "Test Profile" in markdown
        assert "Publication en retard" in markdown
