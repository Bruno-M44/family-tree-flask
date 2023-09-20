# family-tree-flask

## Résumé

API permettant la gestion d'arbres généalogiques. L'API est actuellement opérationelle mais est encore en phase de développement.
Ceci constitue la partie back d'une application front en développement.

## Développement local


### Prérequis

- Compte GitHub avec accès en lecture à ce repository
- Git CLI
- SQLite3 CLI
- Interpréteur Python, version 3.10 ou supérieure
- Postman


#### Cloner le repository

- `git clone https://github.com/Bruno-M44/family-tree-flask.git`

#### Créer l'environnement virtuel

- `python -m venv venv`
- `apt-get install python3-venv` (Si l'étape précédente comporte des erreurs avec un paquet non trouvé sur Ubuntu)
- Activer l'environnement `source venv/bin/activate`
- Confirmer que la commande `python` exécute l'interpréteur Python dans l'environnement virtuel
`which python`
- Confirmer que la version de l'interpréteur Python est la version 3.10 ou supérieure `python --version`
- Confirmer que la commande `pip` exécute l'exécutable pip dans l'environnement virtuel, `which pip`
- Pour désactiver l'environnement, `deactivate`

#### Exécuter le site

- `source venv/bin/activate`
- `pip install --requirement requirements.txt`
- `python run.py runserver`
- Utiliser Postman et connectez-vous à la documentation suivante : https://api.postman.com/collections/19186844-1ebdf63c-b862-4b3e-ad8e-c48f76b97741?access_key=PMAT-01HAS7YWA1XFQS74G4WQTAC2CV
Tous les endpoints sont décrits. 
- Pour utiliser l'API vous devrez d'abord vous créer un compte via http://127.0.0.1:5000/user (POST)
- Les endpoints sont préremplis avec des exemples.
- Une fois le compte créé, vous devrez vous authentifier pour récupérer le jeton JWT via http://127.0.0.1:5000/user (POST).
Ce jeton servira à vous authentifier sur les autres endpoints.
