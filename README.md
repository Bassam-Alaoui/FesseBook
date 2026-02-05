# FesseBook

Agent IA d'orchestration marketing pour la gestion de profils Facebook personnels.

## Objectif

FesseBook centralise et automatise l'organisation éditoriale et le suivi d'activité de plus de 30 profils Facebook personnels via :
- **Notion** : Base de données centrale (CRM social + calendrier éditorial + performance)
- **Gmail** : Notifications, validations, relances, rapports
- **Hootsuite** : Veille, analytics globaux (optionnel)

> **Important** : Les profils Facebook sont des profils personnels (pas des pages). Aucune publication automatique n'est effectuée. Toute publication doit être réalisée manuellement par un humain.

## Fonctionnalités

### 1. Planification Hebdomadaire
- Analyse automatique du calendrier éditorial Notion
- Détection des profils sans contenu planifié
- Génération de posts adaptés à chaque profil
- Remplissage automatique du calendrier

### 2. Workflow de Validation
- Envoi automatique des demandes de validation par email
- Suivi des statuts de validation
- Mise à jour automatique dans Notion

### 3. Publication Guidée (Humaine)
- Rappels de publication le jour J avec :
  - Texte prêt à copier-coller
  - Média suggéré
  - Lien direct vers le profil Facebook
- Confirmation de publication manuelle

### 4. Suivi de Performance
- Demande automatique des métriques 24-48h après publication
- Enregistrement dans Notion
- Génération de rapports hebdomadaires avec insights

## Installation

```bash
# Cloner le repository
git clone https://github.com/votre-org/fessebook.git
cd fessebook

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -e .

# Pour le développement
pip install -e ".[dev]"
```

## Configuration

1. Copier le fichier d'exemple :
```bash
cp .env.example .env
```

2. Configurer les variables d'environnement dans `.env` :

### Notion
- Créer une intégration sur https://www.notion.so/my-integrations
- Partager les bases de données avec l'intégration
- Renseigner `NOTION_TOKEN` et les IDs des bases

### Gmail
- Créer un projet Google Cloud
- Activer l'API Gmail
- Télécharger le fichier `credentials.json`
- Placer le fichier à la racine du projet

## Structure des Bases Notion

### Base "Profils clients"
| Propriété | Type | Description |
|-----------|------|-------------|
| Nom du client | Title | Nom du client |
| Profil Facebook | URL | Lien du profil |
| Responsable | Text | Nom du responsable |
| Email responsable | Email | Email du responsable |
| Type de contenu | Select | professionnel, lifestyle, etc. |
| Fréquence | Select | quotidien, 2_par_semaine, etc. |
| Statut | Select | actif, inactif, en_pause |
| Dernière publication | Date | Date du dernier post |

### Base "Calendrier éditorial"
| Propriété | Type | Description |
|-----------|------|-------------|
| Texte du post | Text | Contenu du post |
| Date de publication | Date | Date prévue |
| Profil | Relation | Lien vers Profils clients |
| Statut | Select | a_valider, valide, publie, etc. |
| Type média | Select | image, video, aucun |

### Base "Performance"
| Propriété | Type | Description |
|-----------|------|-------------|
| Post | Relation | Lien vers Calendrier éditorial |
| Profil | Relation | Lien vers Profils clients |
| Likes | Number | Nombre de likes |
| Commentaires | Number | Nombre de commentaires |
| Partages | Number | Nombre de partages |

## Utilisation

### Interface CLI

```bash
# Voir l'état du système
fessebook status

# Lister les profils
fessebook profiles
fessebook profiles --at-risk

# Lister les posts
fessebook posts
fessebook posts --today
fessebook posts --overdue

# Planification
fessebook plan
fessebook plan --week 10 --year 2024

# Validation
fessebook validate

# Rappels de publication
fessebook remind

# Confirmer une publication
fessebook confirm POST_ID --email responsable@email.com

# Métriques
fessebook metrics
fessebook record-metrics POST_ID --likes 25 --comments 5 --shares 3

# Rapports
fessebook report
fessebook report --send --email manager@email.com

# Routines automatiques
fessebook daily   # Routine quotidienne
fessebook weekly  # Routine hebdomadaire

# Scheduler
fessebook scheduler start  # Démarrer le planificateur
fessebook scheduler list   # Voir les tâches
fessebook scheduler run --job daily_routine  # Exécuter une tâche
```

### Intégration Python

```python
from fessebook.orchestrator import MarketingOrchestrator

# Initialiser l'orchestrateur
orchestrator = MarketingOrchestrator()

# Analyser l'état actuel
state = orchestrator.analyze_current_state()
print(f"Profils actifs: {state['summary']['active_profiles']}")
print(f"Posts en retard: {state['summary']['overdue_posts']}")

# Exécuter la planification
result = orchestrator.run_weekly_planning()
print(f"Posts créés: {result['posts_created']}")

# Envoyer les validations
orchestrator.send_validation_requests()

# Générer un rapport
report = orchestrator.generate_weekly_report()
print(report.to_markdown())
```

## Tâches Planifiées

Le scheduler exécute automatiquement :

| Tâche | Fréquence | Description |
|-------|-----------|-------------|
| Rappels de publication | 8h00 et 9h30 | Envoi des rappels pour les posts du jour |
| Demandes de métriques | 18h00 quotidien | Demande les métriques des posts récents |
| Vérification inactivité | 9h00 quotidien | Alerte les profils inactifs |
| Planification | Lundi 7h00 | Planification de la semaine |
| Rapport hebdomadaire | Vendredi 17h00 | Envoi du rapport de synthèse |

## Architecture

```
src/fessebook/
├── __init__.py
├── config.py              # Configuration centralisée
├── cli.py                 # Interface ligne de commande
├── models/
│   ├── profile.py         # Modèle profil client
│   ├── post.py            # Modèle post/calendrier
│   ├── performance.py     # Modèle performance
│   └── report.py          # Modèle rapport
├── services/
│   ├── notion_service.py  # Intégration Notion
│   ├── gmail_service.py   # Intégration Gmail
│   └── content_generator.py # Génération de contenu
└── orchestrator/
    ├── marketing_orchestrator.py  # Orchestrateur principal
    └── scheduler.py               # Planificateur de tâches
```

## Règles de Comportement

L'agent respecte ces principes :
- Être proactif et structuré
- Prioriser les profils inactifs ou en retard
- Rédiger dans un style clair, humain et engageant
- Adapter le ton à chaque client
- Produire des rapports synthétiques et actionnables
- **Ne jamais tenter de contourner les règles Facebook**
- **Toujours privilégier l'orchestration humaine**

## Licence

MIT License - Voir [LICENSE](LICENSE) pour plus de détails.
