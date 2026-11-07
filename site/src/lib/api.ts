/**
 * Cliente da API do backend (FastAPI). Roda só no servidor.
 *
 * Respostas ficam em cache por minutos ('use cache' + cacheLife): as páginas saem prontas
 * em HTML (bom para o Google) e se atualizam sozinhas. Se a API estiver fora, as funções
 * devolvem vazio/null em vez de derrubar a página.
 */
import { cacheLife, cacheTag } from "next/cache";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type EditalResumo = {
  id: number;
  tipo: string;
  titulo: string | null;
  orgao: string | null;
  banca: string | null;
  uf: string | null;
  salario_max: string | null; // Decimal do backend chega como string
  vagas_total: number | null;
  inscricao_inicio: string | null;
  inscricao_fim: string | null;
  data_prova: string | null;
  fonte: string;
  data_publicacao: string;
  url_publicacao: string | null;
};

export type Cargo = {
  nome: string;
  escolaridade: string;
  vagas: number | null;
  cadastro_reserva: boolean;
  salario: string | null;
};

export type EditalDetalhe = EditalResumo & {
  numero_edital: string | null;
  cidades: string[];
  taxa_inscricao: string | null;
  link_inscricao: string | null;
  resumo: string | null;
  edital_pai_id: number | null;
  cargos: Cargo[];
};

export type Metricas = {
  usuarios_ativos: number;
  publicacoes_candidatas_lidas: number;
  editais_processados: number;
  editais_de_abertura: number;
  alertas_enviados: number;
  latencia_p50_s: number | null;
};

export type FiltrosBusca = {
  q?: string;
  uf?: string;
  abertos?: boolean;
  pagina?: number;
  limite?: number;
};

async function pedir<T>(caminho: string): Promise<T | null> {
  try {
    const resposta = await fetch(`${API_URL}${caminho}`, { headers: { accept: "application/json" } });
    if (resposta.status === 404) return null;
    if (!resposta.ok) throw new Error(`API ${resposta.status} em ${caminho}`);
    return (await resposta.json()) as T;
  } catch (erro) {
    console.error("[api]", erro);
    return null;
  }
}

export async function buscarEditais(filtros: FiltrosBusca = {}): Promise<EditalResumo[]> {
  "use cache";
  cacheLife("minutes");
  cacheTag("editais");
  const params = new URLSearchParams();
  if (filtros.q) params.set("q", filtros.q);
  if (filtros.uf) params.set("uf", filtros.uf);
  if (filtros.abertos) params.set("abertos", "true");
  params.set("limite", String(filtros.limite ?? 24));
  params.set("pagina", String(filtros.pagina ?? 1));
  return (await pedir<EditalResumo[]>(`/editais?${params}`)) ?? [];
}

export async function buscarEdital(id: number): Promise<EditalDetalhe | null> {
  "use cache";
  cacheLife("minutes");
  cacheTag("editais", `edital-${id}`);
  return pedir<EditalDetalhe>(`/editais/${id}`);
}

export async function buscarMetricas(): Promise<Metricas | null> {
  "use cache";
  cacheLife("hours");
  return pedir<Metricas>("/metricas");
}
