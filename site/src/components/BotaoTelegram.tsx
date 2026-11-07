import { linkTelegram } from "@/config/site";

type Props = {
  texto?: string;
  parametroStart?: string;
  variante?: "solido" | "contorno";
  className?: string;
};

function IconeTelegram() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-5 shrink-0 fill-current">
      <path d="M21.9 4.3 18.8 19c-.2 1-.9 1.3-1.8.8l-4.8-3.6-2.3 2.2c-.3.3-.5.5-1 .5l.3-4.9 8.9-8c.4-.3-.1-.5-.6-.2l-11 6.9-4.7-1.5c-1-.3-1-1 .2-1.5L20.6 3c.9-.3 1.6.2 1.3 1.3Z" />
    </svg>
  );
}

/** Some sozinho enquanto o bot não estiver configurado (NEXT_PUBLIC_TELEGRAM_BOT). */
export function BotaoTelegram({
  texto = "Receber alertas no Telegram",
  parametroStart,
  variante = "solido",
  className = "",
}: Props) {
  const href = linkTelegram(parametroStart);
  if (!href) return null;
  const estilo =
    variante === "solido"
      ? "bg-marca text-white hover:bg-marca-forte"
      : "border border-marca text-marca hover:bg-marca-suave";
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 font-semibold transition-colors ${estilo} ${className}`}
    >
      <IconeTelegram />
      {texto}
    </a>
  );
}
