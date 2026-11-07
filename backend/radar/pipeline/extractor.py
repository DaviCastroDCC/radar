"""Extração estruturada de editais com Claude (saída validada por Pydantic)."""

import logging
from datetime import date
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from radar.config import Settings

log = logging.getLogger(__name__)

Escolaridade = Literal["fundamental", "medio", "tecnico", "superior", "nao_informado"]
TipoEdital = Literal[
    "abertura",
    "retificacao",
    "prorrogacao",
    "resultado",
    "convocacao",
    "homologacao",
    "cancelamento",
    "outro",
]


class CargoExtraido(BaseModel):
    nome: str
    escolaridade: Escolaridade
    vagas: int | None = Field(description="Vagas imediatas; null se só cadastro reserva ou não informado")
    cadastro_reserva: bool
    salario: float | None = Field(description="Remuneração inicial em reais")


class EditalExtraido(BaseModel):
    e_concurso: bool = Field(
        description="true se trata de concurso público ou processo seletivo para cargos/empregos"
    )
    tipo: TipoEdital
    orgao: str | None
    banca: str | None
    titulo: str = Field(description="Título curto, ex.: 'Concurso SEEDF 2026 - Professor'")
    numero_edital: str | None = Field(description="Ex.: 'Edital nº 1/2026'")
    edital_referenciado: str | None = Field(
        description="Em retificações/prorrogações, o edital alterado. Ex.: 'Edital nº 1/2026'"
    )
    uf: str | None = Field(description="Sigla da UF das vagas; 'BR' se nacional ou em várias UFs")
    cidades: list[str]
    cargos: list[CargoExtraido]
    inscricao_inicio: str | None = Field(description="AAAA-MM-DD")
    inscricao_fim: str | None = Field(description="AAAA-MM-DD")
    data_prova: str | None = Field(description="AAAA-MM-DD")
    taxa_inscricao: float | None = Field(description="Maior valor de taxa, em reais")
    link_inscricao: str | None
    resumo: str = Field(description="1 a 2 frases para um concurseiro, em português")


SYSTEM = """Você lê publicações de diários oficiais brasileiros e extrai dados de concursos públicos e processos seletivos.

Regras:
- Use somente o que está no texto. Se um dado não aparece, use null (ou lista vazia). Não invente.
- e_concurso = false para licitações, contratos, chamamentos de projetos, nomeações individuais e qualquer coisa que não seja seleção de pessoas para cargos ou empregos.
- tipo:
  - "abertura": edital que abre inscrições.
  - "retificacao": altera ou retifica um edital anterior.
  - "prorrogacao": apenas prorroga prazos de inscrição.
  - "resultado": divulga notas, gabaritos ou classificação.
  - "convocacao": convoca para etapas, posse ou nomeação.
  - "homologacao": homologa o resultado final.
  - "cancelamento": cancela, suspende ou anula o concurso.
  - "outro": qualquer outro caso.
- Datas no formato AAAA-MM-DD.
- salario: remuneração inicial do cargo em reais. Se o edital somar vencimento e gratificações, use o total.
- Liste cada cargo uma vez. Se houver especialidades com o mesmo salário e escolaridade, você pode agrupá-las em um item com os nomes separados por vírgula.
- resumo: uma ou duas frases objetivas, como um aviso para quem estuda para concursos."""


class ErroExtracao(Exception):
    pass


def parse_data(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


class Extrator:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None) -> None:
        self.modelo = settings.extractor_model
        self.effort = settings.extractor_effort
        self.client = client or anthropic.Anthropic()

    def extrair(
        self, *, fonte: str, data: date, orgao: str | None, titulo: str | None, texto: str
    ) -> EditalExtraido:
        conteudo = (
            f'<publicacao fonte="{fonte}" data="{data.isoformat()}" orgao="{orgao or ""}">\n'
            f"<titulo>{titulo or ''}</titulo>\n"
            f"<texto>\n{texto}\n</texto>\n"
            f"</publicacao>"
        )
        try:
            resposta = self.client.messages.parse(
                model=self.modelo,
                max_tokens=16000,
                system=SYSTEM,
                output_config={"effort": self.effort},
                messages=[{"role": "user", "content": conteudo}],
                output_format=EditalExtraido,
            )
        except anthropic.BadRequestError as e:
            raise ErroExtracao(f"requisição inválida: {e.message}") from e
        except anthropic.RateLimitError as e:
            raise ErroExtracao("limite de requisições da API atingido") from e
        except anthropic.APIStatusError as e:
            raise ErroExtracao(f"erro da API ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise ErroExtracao("falha de conexão com a API") from e

        if resposta.stop_reason == "refusal":
            raise ErroExtracao("o modelo recusou a extração")
        if resposta.stop_reason == "max_tokens":
            raise ErroExtracao("resposta cortada por max_tokens")
        if resposta.parsed_output is None:
            raise ErroExtracao("resposta sem JSON válido")

        log.info(
            "extração ok (%s): entrada=%s saída=%s tokens",
            self.modelo,
            resposta.usage.input_tokens,
            resposta.usage.output_tokens,
        )
        return resposta.parsed_output
