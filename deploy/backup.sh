#!/bin/sh
# Backup lógico do Postgres em loop: um dump comprimido a cada INTERVALO_HORAS,
# mantendo RETENCAO_DIAS dias. Restauração: deploy/restaurar.sh
set -eu

RETENCAO_DIAS="${RETENCAO_DIAS:-14}"
INTERVALO_HORAS="${INTERVALO_HORAS:-24}"

while true; do
    arquivo="/backups/radar-$(date -u +%Y%m%d-%H%M%S).dump"
    # Grava em .tmp e só renomeia no fim: um dump pela metade nunca parece válido.
    if pg_dump --format=custom --compress=9 --file="$arquivo.tmp"; then
        mv "$arquivo.tmp" "$arquivo"
        echo "{\"evento\": \"backup_ok\", \"arquivo\": \"$arquivo\", \"tamanho\": \"$(du -h "$arquivo" | cut -f1)\"}"
    else
        rm -f "$arquivo.tmp"
        echo "{\"evento\": \"backup_falhou\"}" >&2
    fi
    find /backups -name 'radar-*.dump' -mtime +"$RETENCAO_DIAS" -delete
    sleep $((INTERVALO_HORAS * 3600))
done
