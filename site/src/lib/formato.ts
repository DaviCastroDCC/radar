/** Formatação no padrão brasileiro e utilitários de URL. Funções puras. */

const MOEDA = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const NUMERO = new Intl.NumberFormat("pt-BR");

export function reais(valor: string | number | null | undefined): string | null {
  if (valor === null || valor === undefined || valor === "") return null;
  const numero = typeof valor === "string" ? Number(valor) : valor;
  return Number.isFinite(numero) ? MOEDA.format(numero) : null;
}

export function numero(valor: number | null | undefined): string | null {
  return valor === null || valor === undefined ? null : NUMERO.format(valor);
}

/** "2026-11-30" -> "30/11/2026" (sem passar por Date, para não sofrer com fuso). */
export function dataBR(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : null;
}

export function periodo(inicio: string | null, fim: string | null): string | null {
  const [a, b] = [dataBR(inicio), dataBR(fim)];
  if (a && b) return `${a} a ${b}`;
  if (b) return `até ${b}`;
  if (a) return `a partir de ${a}`;
  return null;
}

/** Dias inteiros de `hoje` até `isoFim` (negativo = já passou). */
export function diasAte(isoFim: string, hoje: Date): number {
  const [ano, mes, dia] = isoFim.slice(0, 10).split("-").map(Number);
  const fim = Date.UTC(ano, mes - 1, dia);
  const inicio = Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  return Math.round((fim - inicio) / 86_400_000);
}

export function slugify(texto: string | null | undefined): string {
  return (texto ?? "concurso")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

/** URL amigável para o Google: /concursos/123-concurso-seedf-2026 */
export function urlEdital(edital: { id: number; titulo: string | null; orgao?: string | null }): string {
  return `/concursos/${edital.id}-${slugify(edital.titulo ?? edital.orgao)}`;
}

/** "123-concurso-seedf" -> 123 */
export function idDaUrl(segmento: string): number | null {
  const id = Number.parseInt(segmento, 10);
  return Number.isInteger(id) && id > 0 ? id : null;
}

export const ESCOLARIDADE: Record<string, string> = {
  fundamental: "Fundamental",
  medio: "Médio",
  tecnico: "Técnico",
  superior: "Superior",
  nao_informado: "—",
};

export const FONTES: Record<string, string> = {
  dodf: "Diário Oficial do DF",
  dou: "Diário Oficial da União",
  cebraspe: "Cebraspe",
};

export const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
  "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
] as const;
