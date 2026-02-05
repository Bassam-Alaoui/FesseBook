"""
Interface en ligne de commande FesseBook.

Permet d'interagir avec l'orchestrateur marketing depuis le terminal.
"""

import logging
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fessebook.orchestrator import MarketingOrchestrator, TaskScheduler
from fessebook.models.post import PostStatus
from fessebook.models.performance import PerformanceMetrics

# Configuration
app = typer.Typer(
    name="fessebook",
    help="Agent IA d'orchestration marketing pour profils Facebook personnels",
    add_completion=False,
)
console = Console()

# Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def get_orchestrator() -> MarketingOrchestrator:
    """Retourne une instance de l'orchestrateur."""
    return MarketingOrchestrator()


# ===========================================
# COMMANDES D'ANALYSE
# ===========================================


@app.command("status")
def show_status():
    """Affiche l'état actuel du système."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Analyse en cours...", total=None)
        orchestrator = get_orchestrator()
        state = orchestrator.analyze_current_state()

    # Résumé
    summary = state["summary"]
    console.print(Panel.fit(
        f"""[bold blue]FesseBook - État du Système[/bold blue]

[green]Profils actifs:[/green] {summary['active_profiles']}/{summary['total_profiles']}
[yellow]Posts à valider:[/yellow] {summary['posts_awaiting_validation']}
[cyan]Posts à publier aujourd'hui:[/cyan] {summary['posts_to_publish_today']}
[red]Posts en retard:[/red] {summary['overdue_posts']}
[orange1]Profils à risque:[/orange1] {summary['profiles_at_risk']}
""",
        title="Résumé",
    ))

    # Actions prioritaires
    if state["actions"]:
        table = Table(title="Actions Prioritaires")
        table.add_column("Priorité", style="bold")
        table.add_column("Type")
        table.add_column("Profil")
        table.add_column("Description")

        priority_styles = {
            "urgent": "red",
            "haute": "yellow",
            "moyenne": "cyan",
            "basse": "green",
        }

        for action in state["actions"][:10]:
            style = priority_styles.get(action.priority.value, "white")
            table.add_row(
                f"[{style}]{action.priority.value.upper()}[/{style}]",
                action.type.value,
                action.profile_name or "-",
                action.description,
            )

        console.print(table)


@app.command("profiles")
def list_profiles(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filtrer par statut"),
    at_risk: bool = typer.Option(False, "--at-risk", "-r", help="Afficher uniquement les profils à risque"),
):
    """Liste les profils clients."""
    orchestrator = get_orchestrator()

    if at_risk:
        profiles = orchestrator.notion.get_profiles_at_risk()
        title = "Profils à Risque"
    else:
        profiles = orchestrator.notion.get_all_profiles()
        if status:
            profiles = [p for p in profiles if p.status.value == status]
        title = "Tous les Profils"

    table = Table(title=title)
    table.add_column("Client", style="bold")
    table.add_column("Statut")
    table.add_column("Responsable")
    table.add_column("Dernière pub.")
    table.add_column("Jours")
    table.add_column("Fréquence")

    for profile in profiles:
        status_color = "green" if profile.status.value == "actif" else "red"
        days = str(profile.days_since_last_post) if profile.days_since_last_post else "N/A"
        days_color = "red" if profile.is_overdue() else "green"
        last_pub = profile.last_publication_date.strftime("%d/%m/%Y") if profile.last_publication_date else "Jamais"

        table.add_row(
            profile.client_name,
            f"[{status_color}]{profile.status.value}[/{status_color}]",
            profile.responsible_person,
            last_pub,
            f"[{days_color}]{days}[/{days_color}]",
            profile.publication_frequency.value,
        )

    console.print(table)
    console.print(f"\nTotal: {len(profiles)} profils")


@app.command("posts")
def list_posts(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filtrer par statut"),
    today: bool = typer.Option(False, "--today", "-t", help="Posts du jour uniquement"),
    overdue: bool = typer.Option(False, "--overdue", "-o", help="Posts en retard uniquement"),
):
    """Liste les posts du calendrier éditorial."""
    orchestrator = get_orchestrator()

    if today:
        posts = orchestrator.notion.get_posts_to_publish_today()
        title = "Posts à Publier Aujourd'hui"
    elif overdue:
        posts = orchestrator.notion.get_overdue_posts()
        title = "Posts en Retard"
    elif status:
        try:
            post_status = PostStatus(status)
            posts = orchestrator.notion.get_posts_by_status(post_status)
            title = f"Posts - {status}"
        except ValueError:
            console.print(f"[red]Statut invalide: {status}[/red]")
            return
    else:
        posts = orchestrator.notion.get_all_posts()
        title = "Tous les Posts"

    table = Table(title=title)
    table.add_column("Date", style="bold")
    table.add_column("Profil")
    table.add_column("Statut")
    table.add_column("Contenu (aperçu)")

    status_colors = {
        "a_valider": "yellow",
        "valide": "green",
        "a_publier": "cyan",
        "publie": "blue",
        "en_retard": "red",
        "rejete": "red",
    }

    for post in posts[:20]:  # Limiter à 20
        color = status_colors.get(post.status.value, "white")
        content_preview = post.content[:50] + "..." if len(post.content) > 50 else post.content

        table.add_row(
            post.scheduled_date.strftime("%d/%m %H:%M"),
            post.profile_name,
            f"[{color}]{post.status.value}[/{color}]",
            content_preview,
        )

    console.print(table)
    console.print(f"\nTotal: {len(posts)} posts")


# ===========================================
# COMMANDES D'ACTION
# ===========================================


@app.command("plan")
def run_planning(
    week: Optional[int] = typer.Option(None, "--week", "-w", help="Numéro de semaine"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Année"),
):
    """Exécute la planification hebdomadaire."""
    orchestrator = get_orchestrator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Planification en cours...", total=None)
        result = orchestrator.run_weekly_planning(week, year)

    console.print(Panel.fit(
        f"""[bold green]Planification Terminée[/bold green]

Semaine: {result['week']}/{result['year']}
Profils traités: {result['profiles_processed']}
Posts créés: {result['posts_created']}
""",
        title="Résultat",
    ))

    if result['posts_by_profile']:
        table = Table(title="Détail par Profil")
        table.add_column("Profil")
        table.add_column("Existants")
        table.add_column("Créés")
        table.add_column("Total")

        for profile, data in result['posts_by_profile'].items():
            table.add_row(
                profile,
                str(data['existing']),
                str(data['created']),
                str(data['total']),
            )

        console.print(table)


@app.command("validate")
def send_validations():
    """Envoie les demandes de validation."""
    orchestrator = get_orchestrator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Envoi des demandes...", total=None)
        result = orchestrator.send_validation_requests()

    console.print(f"[green]Emails envoyés: {result['sent']}[/green]")
    console.print(f"Posts concernés: {result['posts']}")

    if result.get('errors'):
        console.print("[red]Erreurs:[/red]")
        for error in result['errors']:
            console.print(f"  - {error}")


@app.command("remind")
def send_reminders():
    """Envoie les rappels de publication."""
    orchestrator = get_orchestrator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Envoi des rappels...", total=None)
        result = orchestrator.send_publication_reminders()

    console.print(f"[green]Rappels envoyés: {result['sent']}[/green]")

    if result['posts']:
        for post_info in result['posts']:
            console.print(f"  - {post_info['profile']} ({post_info['scheduled_time']})")


@app.command("confirm")
def confirm_publication(
    post_id: str = typer.Argument(..., help="ID du post publié"),
    email: str = typer.Option(..., "--email", "-e", help="Email de confirmation"),
):
    """Confirme qu'un post a été publié."""
    orchestrator = get_orchestrator()

    success = orchestrator.confirm_publication(post_id, email)

    if success:
        console.print(f"[green]Publication confirmée pour le post {post_id}[/green]")
    else:
        console.print(f"[red]Erreur lors de la confirmation[/red]")


@app.command("metrics")
def request_metrics():
    """Envoie les demandes de métriques."""
    orchestrator = get_orchestrator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Envoi des demandes...", total=None)
        result = orchestrator.send_metrics_requests()

    console.print(f"[green]Demandes envoyées: {result['sent']}[/green]")


@app.command("record-metrics")
def record_metrics(
    post_id: str = typer.Argument(..., help="ID du post"),
    likes: int = typer.Option(0, "--likes", "-l"),
    comments: int = typer.Option(0, "--comments", "-c"),
    shares: int = typer.Option(0, "--shares", "-s"),
    messages: int = typer.Option(0, "--messages", "-m"),
    observations: str = typer.Option("", "--obs", "-o"),
):
    """Enregistre les métriques d'un post."""
    orchestrator = get_orchestrator()

    metrics = PerformanceMetrics(
        likes=likes,
        comments=comments,
        shares=shares,
        messages_received=messages,
    )

    success = orchestrator.record_metrics(post_id, metrics, observations)

    if success:
        console.print(f"[green]Métriques enregistrées pour le post {post_id}[/green]")
        console.print(f"  Likes: {likes}, Commentaires: {comments}, Partages: {shares}")
    else:
        console.print(f"[red]Erreur lors de l'enregistrement[/red]")


# ===========================================
# COMMANDES DE RAPPORT
# ===========================================


@app.command("report")
def generate_report(
    week: Optional[int] = typer.Option(None, "--week", "-w"),
    year: Optional[int] = typer.Option(None, "--year", "-y"),
    send: bool = typer.Option(False, "--send", "-s", help="Envoyer par email"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="Email destinataire"),
):
    """Génère le rapport hebdomadaire."""
    orchestrator = get_orchestrator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Génération du rapport...", total=None)
        report = orchestrator.generate_weekly_report(week, year)

    # Afficher le rapport
    console.print(Panel.fit(
        f"""[bold blue]Rapport Hebdomadaire - S{report.week_number}/{report.year}[/bold blue]

[bold]Période:[/bold] {report.period_start.strftime('%d/%m')} - {report.period_end.strftime('%d/%m/%Y')}

[bold]Profils:[/bold]
  - Actifs: {report.active_profiles}/{report.total_profiles}

[bold]Publications:[/bold]
  - Publiées: {report.total_posts_published}/{report.total_posts_planned}
  - Taux: {report.publication_rate:.1f}%
  - En retard: {report.total_posts_overdue}

[bold]Engagement:[/bold]
  - Likes: {report.total_likes}
  - Commentaires: {report.total_comments}
  - Partages: {report.total_shares}
  - Moyenne/post: {report.average_engagement_per_post:.1f}
""",
        title="Résumé",
    ))

    # Top performers
    if report.top_performers:
        table = Table(title="Top Performances")
        table.add_column("Rang")
        table.add_column("Profil")
        table.add_column("Score")

        for i, p in enumerate(report.top_performers[:5], 1):
            table.add_row(str(i), p.profile_name, f"{p.engagement_score:.0f}")

        console.print(table)

    # Profils à risque
    if report.profiles_at_risk:
        console.print("\n[bold red]Profils à Risque:[/bold red]")
        for p in report.profiles_at_risk:
            console.print(f"  - {p.profile_name} ({p.days_since_last_post} jours)")

    # Insights
    if report.key_insights:
        console.print("\n[bold cyan]Points Clés:[/bold cyan]")
        for insight in report.key_insights:
            console.print(f"  - {insight}")

    # Envoyer par email si demandé
    if send:
        recipients = [email] if email else None
        success = orchestrator.send_weekly_report(recipients, week, year)
        if success:
            console.print(f"\n[green]Rapport envoyé par email[/green]")
        else:
            console.print(f"\n[red]Erreur lors de l'envoi[/red]")


# ===========================================
# COMMANDES DE ROUTINE
# ===========================================


@app.command("daily")
def run_daily():
    """Exécute la routine quotidienne complète."""
    orchestrator = get_orchestrator()

    console.print("[bold]Exécution de la routine quotidienne...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Routine en cours...", total=None)
        result = orchestrator.run_daily_routine()

    console.print("[green]Routine quotidienne terminée[/green]\n")

    # Résumé
    console.print(f"Rappels de publication envoyés: {result['publication_reminders']['sent']}")
    console.print(f"Demandes de métriques envoyées: {result['metrics_requests']['sent']}")
    console.print(f"Alertes d'inactivité envoyées: {result['inactivity_alerts']['alerts_sent']}")


@app.command("weekly")
def run_weekly():
    """Exécute la routine hebdomadaire complète."""
    orchestrator = get_orchestrator()

    console.print("[bold]Exécution de la routine hebdomadaire...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Routine en cours...", total=None)
        result = orchestrator.run_weekly_routine()

    console.print("[green]Routine hebdomadaire terminée[/green]\n")

    # Résumé
    console.print(f"Posts créés: {result['planning']['posts_created']}")
    console.print(f"Demandes de validation envoyées: {result['validation_requests']['sent']}")
    console.print(f"Rapport hebdomadaire envoyé: {result['weekly_report']['sent']}")


# ===========================================
# SCHEDULER
# ===========================================


@app.command("scheduler")
def manage_scheduler(
    action: str = typer.Argument(..., help="start, stop, list, run"),
    job_id: Optional[str] = typer.Option(None, "--job", "-j", help="ID de la tâche"),
):
    """Gère le planificateur de tâches."""
    scheduler = TaskScheduler()

    if action == "start":
        scheduler.start()
        console.print("[green]Scheduler démarré[/green]")
        console.print("Appuyez sur Ctrl+C pour arrêter...")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            console.print("\n[yellow]Scheduler arrêté[/yellow]")

    elif action == "stop":
        scheduler.stop()
        console.print("[yellow]Scheduler arrêté[/yellow]")

    elif action == "list":
        jobs = scheduler.list_jobs()
        table = Table(title="Tâches Planifiées")
        table.add_column("ID")
        table.add_column("Nom")
        table.add_column("Prochain lancement")
        table.add_column("Déclencheur")

        for job in jobs:
            table.add_row(
                job["id"],
                job["name"],
                job["next_run"] or "N/A",
                job["trigger"],
            )

        console.print(table)

    elif action == "run":
        if not job_id:
            console.print("[red]Spécifiez un job_id avec --job[/red]")
            return
        success = scheduler.run_job_now(job_id)
        if success:
            console.print(f"[green]Tâche {job_id} exécutée[/green]")
        else:
            console.print(f"[red]Tâche {job_id} non trouvée[/red]")

    else:
        console.print(f"[red]Action inconnue: {action}[/red]")
        console.print("Actions disponibles: start, stop, list, run")


# ===========================================
# POINT D'ENTRÉE
# ===========================================


if __name__ == "__main__":
    app()
