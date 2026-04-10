# family-tree-flask

API REST pour la gestion d'arbres généalogiques. Partie back-end d'une application full-stack en développement.

## Stack technique

| Composant | Technologie |
|---|---|
| Framework | Flask 3.x |
| Base de données | PostgreSQL 16 (psycopg3) |
| ORM | SQLAlchemy 2.x + Flask-SQLAlchemy |
| Authentification | JWT (Flask-JWT-Extended) |
| Sérialisation | Marshmallow + marshmallow-sqlalchemy |
| Conteneurisation | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## Prérequis

- Docker et Docker Compose
- Python 3.12+ (pour le développement local et les tests)
- Git

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/Bruno-M44/family-tree-flask.git
cd family-tree-flask
```

### 2. Configurer les variables d'environnement

Créer un fichier `.env` à la racine du projet :

```env
DB_URL=postgresql+psycopg://postgres:postgres@flask_db:5432/postgres
JWT_SECRET_KEY=<clé aléatoire longue>
```

Pour générer une clé JWT sécurisée :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Développement local

### Lancer l'application

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build -d
```

L'API est disponible sur `http://localhost:4000`.

### Initialiser la base de données

À faire au premier lancement ou après un `down -v` :

```bash
docker exec -it flask_app flask command_app init-db
```

### Arrêter l'application

```bash
docker compose down
```

---

## Tests

Les tests utilisent SQLite en mémoire et s'exécutent **en dehors de Docker**, directement avec le venv local. Aucune instance PostgreSQL n'est nécessaire.

### Installation des dépendances de développement

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Lancer les tests

```bash
pytest tests/ -v
```

### Avec le rapport de couverture

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Variables d'environnement

| Variable | Description | Obligatoire |
|---|---|---|
| `DB_URL` | URL de connexion PostgreSQL | Oui |
| `JWT_SECRET_KEY` | Clé secrète pour signer les tokens JWT | Oui |
| `CORS_ORIGINS` | Origines autorisées pour le CORS (ex: `https://family-tree.io`) | Non (défaut : `*`) |

---

## Endpoints API

Tous les endpoints protégés requièrent un header `Authorization: Bearer <token>`.

### Authentification

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/login` | Obtenir un token JWT | Non |
| `POST` | `/refresh` | Renouveler le token | Oui |

### Utilisateur

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/user` | Créer un compte | Non |
| `GET` | `/user` | Récupérer son profil | Oui |
| `PUT` | `/user` | Modifier son profil | Oui |
| `DELETE` | `/user` | Supprimer son compte | Oui |

### Arbres généalogiques

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/family_trees` | Lister ses arbres | Oui |
| `POST` | `/family_tree` | Créer un arbre | Oui |
| `GET` | `/family_trees/<id>` | Détail d'un arbre | Oui |
| `PUT` | `/family_trees/<id>` | Modifier un arbre | Oui |
| `DELETE` | `/family_trees/<id>` | Supprimer un arbre | Oui |

### Cellules (membres)

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/family_trees/<id>/family_tree_cells` | Lister les membres | Oui |
| `POST` | `/family_trees/<id>/family_tree_cells` | Ajouter un membre | Oui |
| `GET` | `/family_trees/<id>/family_tree_cells/<id>` | Détail d'un membre | Oui |
| `PUT` | `/family_trees/<id>/family_tree_cells/<id>` | Modifier un membre | Oui |
| `DELETE` | `/family_trees/<id>/family_tree_cells/<id>` | Supprimer un membre | Oui |

### Photos

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/family_tree_cells/<id>/pictures` | Lister les photos | Oui |
| `POST` | `/family_trees/<id>/family_tree_cells/<id>/pictures` | Uploader une photo | Oui |
| `GET` | `/family_trees/<id>/family_tree_cells/<id>/pictures/<id>` | Détail d'une photo | Oui |
| `PUT` | `/family_trees/<id>/family_tree_cells/<id>/pictures/<id>` | Modifier une photo | Oui |
| `GET` | `/family_trees/<id>/family_tree_cells/<id>/pictures/<id>/secure` | Télécharger une photo | Oui |
| `DELETE` | `/family_trees/<id>/family_tree_cells/<id>/pictures/<id>/delete` | Supprimer une photo | Oui |

### Animaux

| Méthode | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/family_tree_cells/<id>/pets` | Lister les animaux | Oui |
| `POST` | `/family_tree_cells/<id>/pets` | Ajouter un animal | Oui |
| `GET` | `/family_tree_cells/<id>/pets/<id>` | Détail d'un animal | Oui |
| `PUT` | `/family_tree_cells/<id>/pets/<id>` | Modifier un animal | Oui |
| `DELETE` | `/family_tree_cells/<id>/pets/<id>` | Supprimer un animal | Oui |
| `GET` | `/pets/<id>/pets_pictures` | Lister les photos d'un animal | Oui |
| `POST` | `/pets/<id>/pets_pictures` | Uploader une photo | Oui |
| `GET` | `/pets/<id>/pets_pictures/<id>/download` | Télécharger une photo | Oui |
| `DELETE` | `/pets/<id>/pets_pictures/<id>/delete` | Supprimer une photo | Oui |

---

## Format des dates

Toutes les dates sont au format `dd/mm/yyyy` (ex: `25/12/1990`).

---

## Déploiement

Le déploiement est automatisé via GitHub Actions au push sur `main`.

Le pipeline :
1. Lance les tests
2. Si les tests passent, déploie sur le VPS via SSH

Les secrets à configurer dans GitHub Actions :

| Secret | Description |
|---|---|
| `VPS_HOST` | Adresse IP ou domaine du VPS |
| `VPS_USER` | Utilisateur SSH |
| `VPS_SSH_KEY` | Clé privée SSH |
| `JWT_SECRET_KEY` | Clé JWT de production |

### Lancer manuellement en production

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build flask_app
```
