from os import environ
from dotenv import load_dotenv


load_dotenv()  # charge le .env dans l'environnement

SQLALCHEMY_DATABASE_URI = environ.get('DB_URL')
JWT_SECRET_KEY = environ.get('JWT_SECRET_KEY')
ENCRYPTION_KEY = environ.get('ENCRYPTION_KEY')
RESEND_API_KEY = environ.get('RESEND_API_KEY')
FRONTEND_URL = environ.get('FRONTEND_URL', 'http://localhost:5173')
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 Mo

# Racines de stockage des photos (personnes / animaux) sur disque. Surchargeable
# par env var — les tests DOIVENT pointer ailleurs que la valeur par défaut de prod,
# pour ne jamais écrire/déplacer des fichiers sous les mêmes chemins que de vraies
# données (les IDs de la base de test repartent de 1 à chaque test, donc collision
# quasi garantie avec de vrais id_family_tree/id_family_tree_cell si le chemin est partagé).
PICTURES_ROOT = environ.get('PICTURES_ROOT', '/pictures')
PET_PICTURES_ROOT = environ.get('PET_PICTURES_ROOT', '/pet_pictures')
AVATARS_ROOT = environ.get('AVATARS_ROOT', '/avatars')

SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 2,
    "max_overflow": 3,
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 10,
}
