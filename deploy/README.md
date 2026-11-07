# Deploy e operação

Uma VM pequena com Docker roda tudo: banco, worker, bot, API, HTTPS e backup. É suficiente
para milhares de usuários. ECS/RDS na AWS só quando houver carga ou exigência que justifique.

## 1. Escolher a VM

| Provedor | Plano sugerido | Custo aproximado |
|---|---|---|
| Hetzner (Alemanha/EUA) | CX22 (2 vCPU, 4 GB) | ~€ 4/mês |
| AWS Lightsail (São Paulo) | 2 GB | ~US$ 10/mês |
| Oracle Cloud | Ampere A1 (Always Free) | grátis, com limites |
| Magalu Cloud / Locaweb (Brasil) | 2 vCPU, 4 GB | ~R$ 60–100/mês |

Requisitos: Ubuntu 24.04, 2 GB de RAM ou mais, 40 GB de disco, IP público.

## 2. Preparar a VM (uma vez)

```bash
# como root, na VM
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
adduser radar && usermod -aG docker radar

# firewall: só SSH e web
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw enable

# atualizações de segurança automáticas
apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades
```

Desative login por senha no SSH (só chave): `PasswordAuthentication no` em `/etc/ssh/sshd_config`.

## 3. DNS

Crie um registro **A** apontando o domínio da API (ex.: `api.radarconcurso.com.br`) para o
IP da VM. O Caddy emite o certificado HTTPS sozinho na primeira subida.

## 4. Subir

```bash
# como usuário radar, na VM
git clone https://github.com/DaviCastroDCC/radar.git && cd radar
cp .env.example .env && nano .env      # preencha tudo (seção "Produção" incluída)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl https://SEU_DOMINIO/saude
```

Variáveis obrigatórias em produção: `POSTGRES_PASSWORD` (gere com `openssl rand -base64 32`),
`DOMINIO`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `INLABS_EMAIL`, `INLABS_PASSWORD`,
`ADMIN_CHAT_ID`, `CONTATO_PRIVACIDADE`.

## 5. Monitor externo (5 minutos, grátis)

Cadastre `https://SEU_DOMINIO/saude` no [UptimeRobot](https://uptimerobot.com) ou no
[Healthchecks.io](https://healthchecks.io), checando a cada 5 min e avisando por e-mail ou
Telegram. Ele responde **503** se houver problema crítico, inclusive se o worker morrer.

## Atualizar para uma nova versão

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

O serviço `migrate` aplica as migrations antes de worker, bot e API voltarem.

## Backups

- Um dump por dia em `./backups`, mantido por 14 dias (`BACKUP_RETENCAO_DIAS`).
- **Cópia fora da VM é obrigatória**: se a VM sumir, os backups somem junto. Opção simples:
  [rclone](https://rclone.org) para Backblaze B2 ou S3, num cron diário:
  `rclone copy ./backups b2:radar-backups --max-age 48h`
- Restauração (testada):

```bash
docker compose -f docker-compose.prod.yml stop worker bot api
./deploy/restaurar.sh backups/radar-AAAAMMDD-HHMMSS.dump
docker compose -f docker-compose.prod.yml up -d
```

Faça um **teste de restauração por mês**: backup que nunca foi restaurado é só esperança.

## Comandos do dia a dia

```bash
C="docker compose -f docker-compose.prod.yml"
$C logs -f worker                          # acompanhar a coleta
$C run --rm worker python -m radar.worker saude
$C exec db psql -U radar                   # console do banco
curl https://SEU_DOMINIO/metricas          # números do produto
```

## O que já vem endurecido

| Item | Como |
|---|---|
| HTTPS | Caddy + Let's Encrypt, HSTS, HTTP→HTTPS (308) |
| Banco | Sem porta exposta; senha obrigatória |
| Containers | Processo sem root (uid 10001); imagem sem ferramentas de teste |
| Disco | Rotação de logs (5 × 20 MB por serviço) |
| Reinício | `restart: unless-stopped` e healthcheck na API |
