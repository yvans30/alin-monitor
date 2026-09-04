FROM python:3.11-slim

WORKDIR /app

# TARGETARCH (fourni par buildkit) sélectionne le binaire sops pour l'arch
# réelle du build : un binaire amd64 émulé sur arm64 échoue silencieusement
# (bug connu de l'émulation crypto QEMU).
ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends age curl \
    && curl -fsSL "https://github.com/getsops/sops/releases/download/v3.13.3/sops-v3.13.3.linux.${TARGETARCH}" \
       -o /usr/local/bin/sops \
    && chmod +x /usr/local/bin/sops \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/
COPY .env.enc ./
COPY scripts/run.sh ./scripts/run.sh

RUN chmod +x ./scripts/run.sh

# Pas d'affichage graphique ici : le fallback Playwright manuel (MFA/CAPTCHA)
# est désactivé par défaut sur cette image (ENABLE_MANUAL_FALLBACK=false dans
# .env), donc Chromium n'est pas installé. Cf. README.md.
ENV ENABLE_MANUAL_FALLBACK=false

CMD ["./scripts/run.sh"]
