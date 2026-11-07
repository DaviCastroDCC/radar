"""Mapeamento ORM. A fonte da verdade do schema são as migrations (backend/migrations);
o teste tests/test_migrations.py garante que estes models continuam idênticos ao banco."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    # Padrões iguais aos do Postgres: TEXT (não VARCHAR) e TIMESTAMPTZ (sempre com fuso).
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text(), datetime: DateTime(timezone=True)}


def _fk(alvo: str, *, cascata: bool = False, **kwargs: Any):
    return mapped_column(BigInteger, ForeignKey(alvo, ondelete="CASCADE" if cascata else None), **kwargs)


def _agora():
    return mapped_column(server_default=func.now())


class Publicacao(Base):
    __tablename__ = "publicacoes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fonte: Mapped[str]
    id_externo: Mapped[str]
    data_publicacao: Mapped[date]
    secao: Mapped[str | None]
    orgao: Mapped[str | None]
    tipo_ato: Mapped[str | None]
    titulo: Mapped[str | None]
    url: Mapped[str | None]
    texto: Mapped[str]
    hash_texto: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="pendente")
    score_detector: Mapped[int | None]
    tentativas: Mapped[int] = mapped_column(server_default="0")
    erro: Mapped[str | None]
    coletada_em: Mapped[datetime] = _agora()
    processada_em: Mapped[datetime | None]


class Edital(Base):
    __tablename__ = "editais"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    publicacao_id: Mapped[int] = _fk("publicacoes.id")
    edital_pai_id: Mapped[int | None] = _fk("editais.id")
    tipo: Mapped[str]
    orgao: Mapped[str | None]
    banca: Mapped[str | None]
    titulo: Mapped[str | None]
    numero_edital: Mapped[str | None]
    edital_referenciado: Mapped[str | None]
    uf: Mapped[str | None]
    cidades: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    inscricao_inicio: Mapped[date | None]
    inscricao_fim: Mapped[date | None]
    data_prova: Mapped[date | None]
    taxa_inscricao: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    salario_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    vagas_total: Mapped[int | None]
    link_inscricao: Mapped[str | None]
    resumo: Mapped[str | None]
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB)
    modelo: Mapped[str | None]
    criado_em: Mapped[datetime] = _agora()

    publicacao: Mapped[Publicacao] = relationship()
    cargos: Mapped[list["Cargo"]] = relationship(back_populates="edital", cascade="all, delete-orphan")


class Cargo(Base):
    __tablename__ = "cargos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    edital_id: Mapped[int] = _fk("editais.id", cascata=True)
    nome: Mapped[str]
    escolaridade: Mapped[str]
    vagas: Mapped[int | None]
    cadastro_reserva: Mapped[bool] = mapped_column(server_default="false")
    salario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    edital: Mapped[Edital] = relationship(back_populates="cargos")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    nome: Mapped[str | None]
    email: Mapped[str | None]
    plano: Mapped[str] = mapped_column(server_default="free")
    ativo: Mapped[bool] = mapped_column(server_default="true")
    criado_em: Mapped[datetime] = _agora()

    filtros: Mapped[list["Filtro"]] = relationship(back_populates="usuario", passive_deletes=True)


class Filtro(Base):
    __tablename__ = "filtros"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = _fk("usuarios.id", cascata=True)
    palavras: Mapped[str] = mapped_column(server_default="")
    ufs: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    escolaridades: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    salario_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ativo: Mapped[bool] = mapped_column(server_default="true")
    criado_em: Mapped[datetime] = _agora()

    usuario: Mapped[Usuario] = relationship(back_populates="filtros")


class Acompanhamento(Base):
    __tablename__ = "acompanhamentos"

    usuario_id: Mapped[int] = _fk("usuarios.id", cascata=True, primary_key=True)
    edital_id: Mapped[int] = _fk("editais.id", cascata=True, primary_key=True)
    criado_em: Mapped[datetime] = _agora()


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = _fk("usuarios.id", cascata=True)
    edital_id: Mapped[int] = _fk("editais.id", cascata=True)
    motivo: Mapped[str]
    canal: Mapped[str] = mapped_column(server_default="telegram")
    status: Mapped[str] = mapped_column(server_default="pendente")
    tentativas: Mapped[int] = mapped_column(server_default="0")
    erro: Mapped[str | None]
    criado_em: Mapped[datetime] = _agora()
    enviado_em: Mapped[datetime | None]

    usuario: Mapped[Usuario] = relationship()
    edital: Mapped[Edital] = relationship()


class Coleta(Base):
    __tablename__ = "coletas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fonte: Mapped[str]
    data_ref: Mapped[date]
    iniciada_em: Mapped[datetime] = _agora()
    finalizada_em: Mapped[datetime | None]
    itens_lidos: Mapped[int] = mapped_column(server_default="0")
    itens_novos: Mapped[int] = mapped_column(server_default="0")
    erro: Mapped[str | None]
