/**
 * Identidade do site. O nome é PROVISÓRIO: trocar aqui (ou via variável de ambiente)
 * muda o site inteiro — cabeçalho, títulos, metadados e textos.
 */
export const site = {
  nome: process.env.NEXT_PUBLIC_SITE_NOME ?? "Alerta Edital",
  slogan: "Saiu concurso para você? Você fica sabendo em minutos.",
  descricao:
    "Concursos públicos com inscrições abertas, lidos direto dos diários oficiais e das bancas. " +
    "Receba alertas no Telegram só do que combina com você: cargo, estado e salário.",
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  // Usuário do bot no Telegram (sem @). Vazio = botões de alerta ficam ocultos.
  botTelegram: process.env.NEXT_PUBLIC_TELEGRAM_BOT ?? "",
} as const;

export function linkTelegram(parametroStart?: string): string | null {
  if (!site.botTelegram) return null;
  const base = `https://t.me/${site.botTelegram}`;
  return parametroStart ? `${base}?start=${encodeURIComponent(parametroStart)}` : base;
}
