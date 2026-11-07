# Site público

Next.js 16 (App Router, Cache Components) + TypeScript + Tailwind 4. Consome a API do backend.

```bash
cp .env.example .env.local   # API_URL e, opcionalmente, o bot do Telegram
npm install
npm run dev                  # http://localhost:3000 (backend rodando em :8000)
```

| Rota | O que é | Renderização |
|---|---|---|
| `/` | Início: busca, inscrições abertas, como funciona | Estática, revalida a cada minuto |
| `/concursos` | Busca com filtros (cargo, UF, inscrições abertas) | Casca estática + resultados por requisição |
| `/concursos/[id]-[slug]` | Página do edital (SEO) | Casca estática + dados em cache por minutos |
| `/privacidade` | Resumo da política (LGPD) | Estática |
| `/sitemap.xml`, `/robots.txt` | Para os buscadores | Estáticos, revalidam |

- **Nome provisório:** muda em `src/config/site.ts` (ou `NEXT_PUBLIC_SITE_NOME`).
- **Botões do Telegram** só aparecem com `NEXT_PUBLIC_TELEGRAM_BOT` definido.
- Esta versão do Next.js mudou bastante: antes de mexer, leia `AGENTS.md`.
