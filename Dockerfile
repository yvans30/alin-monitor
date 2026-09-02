FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Outils nécessaires au déchiffrement des secrets
RUN apt-get update \
    && apt-get install -y --no-install-recommends age curl \
    && curl -fsSL https://github.com/getsops/sops/releases/download/v3.13.3/sops-v3.13.3.linux.amd64 \
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

CMD ["./scripts/run.sh"]
