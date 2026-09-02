# Image officielle Playwright : navigateurs + dépendances système déjà installés,
# ce qui évite de gérer manuellement les libs nécessaires à Chromium sous Debian slim.
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

# IMPORTANT : le premier lancement nécessite une authentification manuelle
# (email + mot de passe + éventuelle MFA) dans un navigateur visible. Ce
# n'est pas possible directement dans ce conteneur sans accès graphique
# (X11/VNC). Voir le README, section "Première authentification", pour la
# procédure recommandée (lancer en local hors Docker la première fois, puis
# copier data/storage_state.json avant de démarrer via Docker).

CMD ["python", "-m", "app.main"]
