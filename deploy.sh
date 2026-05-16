#!/bin/bash
set -euo pipefail

REPO="https://github.com/SeydinaBANE/multi-agent-system.git"
DIR="multi-agent-system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀  Déploiement Multi-Agent System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Docker ─────────────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
  echo "→ Installation de Docker…"
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "$USER"
  echo "⚠  Docker installé. Déconnecte-toi et reconnecte-toi, puis relance ce script."
  exit 0
fi

# ── 2. Repo ───────────────────────────────────────────────────────────────
if [ -d "$DIR/.git" ]; then
  echo "→ Mise à jour du repo…"
  git -C "$DIR" pull --ff-only
else
  echo "→ Clonage du repo…"
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

# ── 3. .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠  Fichier .env créé. Renseigne ta clé :"
  echo "   nano .env   →  OPENROUTER_API_KEY=sk-or-..."
  echo ""
  echo "   Puis relance : bash deploy.sh"
  exit 1
fi

if grep -q "^OPENROUTER_API_KEY=$\|^OPENROUTER_API_KEY=your_" .env; then
  echo "❌ OPENROUTER_API_KEY non renseignée dans .env"
  echo "   nano .env   →  OPENROUTER_API_KEY=sk-or-..."
  exit 1
fi

# ── 4. Build + démarrage ──────────────────────────────────────────────────
echo "→ Build et démarrage des services…"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ── 5. Migrations ─────────────────────────────────────────────────────────
echo "→ Migrations base de données…"
sleep 5   # laisser PostgreSQL démarrer
docker compose exec -T api alembic upgrade head

# ── 6. Résultat ───────────────────────────────────────────────────────────
IP=$(curl -s ifconfig.me 2>/dev/null || echo "TON_IP")
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Déployé avec succès !"
echo ""
echo "  Interface  →  http://$IP:8000"
echo "  Swagger    →  http://$IP:8000/docs"
echo "  Health     →  http://$IP:8000/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
