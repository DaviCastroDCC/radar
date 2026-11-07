#!/bin/sh
# Restaura um backup no banco de produção.
#   ./deploy/restaurar.sh backups/radar-20261107-030000.dump
#
# ATENÇÃO: substitui os dados atuais. Pare worker, bot e api antes:
#   docker compose -f docker-compose.prod.yml stop worker bot api
set -eu

ARQUIVO="${1:?uso: $0 <arquivo .dump>}"
[ -f "$ARQUIVO" ] || { echo "arquivo não encontrado: $ARQUIVO" >&2; exit 1; }

COMPOSE="${COMPOSE:-docker compose -f docker-compose.prod.yml}"

echo "Restaurando $ARQUIVO ..."
$COMPOSE exec -T db pg_restore --username=radar --dbname=radar --clean --if-exists --no-owner \
    < "$ARQUIVO"
echo "Pronto. Suba os serviços: $COMPOSE up -d"
