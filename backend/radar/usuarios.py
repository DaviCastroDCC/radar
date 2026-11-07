"""Regras de negócio de usuários: cadastro, consentimento (LGPD), filtros e direitos do titular.

Funções síncronas que abrem a própria transação. O bot chama via asyncio.to_thread e só
formata as respostas; nada aqui conhece o Telegram além do chat_id como identificador.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from radar.db import session_scope
from radar.models import Acompanhamento, Alerta, Edital, Filtro, Usuario
from radar.relogio import agora

# Mude a versão sempre que o texto da política mudar de forma relevante:
# quem aceitou a versão anterior precisa aceitar de novo.
TERMOS_VERSAO = "2026-11-07"

# Usuário que bloqueou o bot ou pausou os alertas tem os dados apagados após este prazo.
RETENCAO_INATIVOS = timedelta(days=180)


class ErroUsuario(Exception):
    """Base dos erros de regra de negócio (o bot transforma em mensagem amigável)."""


class UsuarioNaoCadastrado(ErroUsuario):
    pass


class TermosPendentes(ErroUsuario):
    pass


class LimiteDeFiltros(ErroUsuario):
    def __init__(self, total: int) -> None:
        super().__init__(f"limite de {total} filtros atingido")
        self.total = total


@dataclass(frozen=True)
class FiltroResumo:
    id: int
    palavras: str
    ufs: list[str]
    escolaridades: list[str]
    salario_min: Decimal | None


# ---------------------------------------------------------------------------
# Cadastro e consentimento
# ---------------------------------------------------------------------------
def pode_receber_alertas() -> ColumnElement[bool]:
    """Condição SQL: usuário ativo e com consentimento na versão vigente dos termos."""
    return and_(Usuario.ativo.is_(True), Usuario.termos_versao == TERMOS_VERSAO)


def _buscar(s: Session, chat_id: int) -> Usuario | None:
    return s.scalar(select(Usuario).where(Usuario.telegram_chat_id == chat_id))


def _exigir_consentimento(s: Session, chat_id: int) -> Usuario:
    usuario = _buscar(s, chat_id)
    if usuario is None:
        raise UsuarioNaoCadastrado
    if usuario.termos_versao != TERMOS_VERSAO:
        raise TermosPendentes
    return usuario


def registrar(chat_id: int) -> bool:
    """Cadastra (ou reativa) o usuário. Devolve True se ele já aceitou os termos vigentes."""
    with session_scope() as s:
        s.execute(
            insert(Usuario)
            .values(telegram_chat_id=chat_id)
            .on_conflict_do_update(
                index_elements=["telegram_chat_id"], set_={"ativo": True, "desativado_em": None}
            )
        )
        return _buscar(s, chat_id).termos_versao == TERMOS_VERSAO


def aceitar_termos(chat_id: int) -> None:
    with session_scope() as s:
        usuario = _buscar(s, chat_id)
        if usuario is None:
            raise UsuarioNaoCadastrado
        usuario.termos_aceitos_em = agora()
        usuario.termos_versao = TERMOS_VERSAO


def desativar(usuario: Usuario) -> None:
    """Para de enviar alertas e inicia a contagem do prazo de retenção."""
    usuario.ativo = False
    usuario.desativado_em = agora()


def pausar(chat_id: int) -> None:
    with session_scope() as s:
        usuario = _buscar(s, chat_id)
        if usuario is not None and usuario.ativo:
            desativar(usuario)


# ---------------------------------------------------------------------------
# Filtros e acompanhamentos
# ---------------------------------------------------------------------------
def criar_filtro(
    chat_id: int,
    *,
    palavras: str,
    ufs: list[str],
    escolaridades: list[str],
    salario_min: Decimal | None,
    limite_free: int,
) -> int:
    with session_scope() as s:
        usuario = _exigir_consentimento(s, chat_id)
        total = s.scalar(select(func.count()).select_from(Filtro).where(Filtro.usuario_id == usuario.id))
        if usuario.plano == "free" and total >= limite_free:
            raise LimiteDeFiltros(total)
        filtro = Filtro(
            usuario_id=usuario.id,
            palavras=palavras,
            ufs=ufs,
            escolaridades=escolaridades,
            salario_min=salario_min,
        )
        s.add(filtro)
        s.flush()
        return filtro.id


def listar_filtros(chat_id: int) -> list[FiltroResumo]:
    with session_scope() as s:
        usuario = _buscar(s, chat_id)
        if usuario is None:
            raise UsuarioNaoCadastrado
        filtros = s.scalars(select(Filtro).where(Filtro.usuario_id == usuario.id).order_by(Filtro.id))
        return [
            FiltroResumo(f.id, f.palavras, list(f.ufs), list(f.escolaridades), f.salario_min) for f in filtros
        ]


def remover_filtro(chat_id: int, filtro_id: int) -> bool:
    """Apaga de verdade (não só desativa): filtro removido não deve continuar guardado."""
    with session_scope() as s:
        usuario = _buscar(s, chat_id)
        if usuario is None:
            return False
        resultado = s.execute(
            delete(Filtro).where(Filtro.id == filtro_id, Filtro.usuario_id == usuario.id).returning(Filtro.id)
        )
        return resultado.scalar_one_or_none() is not None


def acompanhar(chat_id: int, edital_id: int) -> bool:
    with session_scope() as s:
        usuario = _exigir_consentimento(s, chat_id)
        if s.get(Edital, edital_id) is None:
            return False
        s.execute(
            insert(Acompanhamento).values(usuario_id=usuario.id, edital_id=edital_id).on_conflict_do_nothing()
        )
        return True


# ---------------------------------------------------------------------------
# Direitos do titular (LGPD art. 18)
# ---------------------------------------------------------------------------
def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def exportar_dados(chat_id: int) -> dict[str, Any] | None:
    """Acesso e portabilidade: tudo o que guardamos sobre o titular, em formato legível."""
    with session_scope() as s:
        usuario = _buscar(s, chat_id)
        if usuario is None:
            return None
        acompanhados = s.execute(
            select(Edital.id, Edital.titulo, Acompanhamento.criado_em)
            .join(Acompanhamento, Acompanhamento.edital_id == Edital.id)
            .where(Acompanhamento.usuario_id == usuario.id)
            .order_by(Acompanhamento.criado_em)
        )
        alertas = s.execute(
            select(Alerta, Edital.titulo)
            .join(Edital, Edital.id == Alerta.edital_id)
            .where(Alerta.usuario_id == usuario.id)
            .order_by(Alerta.id)
        )
        return {
            "gerado_em": agora().isoformat(),
            "usuario": {
                "telegram_chat_id": usuario.telegram_chat_id,
                "email": usuario.email,
                "plano": usuario.plano,
                "ativo": usuario.ativo,
                "cadastrado_em": _iso(usuario.criado_em),
                "termos_aceitos_em": _iso(usuario.termos_aceitos_em),
                "termos_versao": usuario.termos_versao,
                "desativado_em": _iso(usuario.desativado_em),
            },
            "filtros": [
                {
                    "palavras": f.palavras,
                    "ufs": f.ufs,
                    "escolaridades": f.escolaridades,
                    "salario_min": str(f.salario_min) if f.salario_min is not None else None,
                    "criado_em": _iso(f.criado_em),
                }
                for f in s.scalars(select(Filtro).where(Filtro.usuario_id == usuario.id).order_by(Filtro.id))
            ],
            "editais_acompanhados": [
                {"edital_id": id_, "titulo": titulo, "desde": _iso(desde)}
                for id_, titulo, desde in acompanhados
            ],
            "alertas_recebidos": [
                {
                    "edital": titulo,
                    "motivo": a.motivo,
                    "status": a.status,
                    "enviado_em": _iso(a.enviado_em),
                }
                for a, titulo in alertas
            ],
        }


def apagar(chat_id: int) -> bool:
    """Eliminação: remove o usuário; filtros, acompanhamentos e alertas saem em cascata no banco."""
    with session_scope() as s:
        resultado = s.execute(
            delete(Usuario).where(Usuario.telegram_chat_id == chat_id).returning(Usuario.id)
        )
        return resultado.scalar_one_or_none() is not None


def purgar_inativos(referencia: datetime | None = None) -> int:
    """Política de retenção: apaga quem está inativo há mais de RETENCAO_INATIVOS."""
    limite = (referencia or agora()) - RETENCAO_INATIVOS
    with session_scope() as s:
        apagados = s.scalars(
            delete(Usuario)
            .where(Usuario.ativo.is_(False), Usuario.desativado_em < limite)
            .returning(Usuario.id)
        ).all()
        return len(apagados)
