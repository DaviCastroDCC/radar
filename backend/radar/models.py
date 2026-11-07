"""Mapeamento ORM das tabelas definidas em db/schema.sql (a fonte da verdade do schema)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


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
    coletada_em: Mapped[datetime] = mapped_column(server_default="now()")
    processada_em: Mapped[datetime | None]


class Edital(Base):
    __tablename__ = "editais"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    publicacao_id: Mapped[int] = mapped_column(ForeignKey("publicacoes.id"))
    edital_pai_id: Mapped[int | None] = mapped_column(ForeignKey("editais.id"))
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
    taxa_inscricao: Mapped[Decimal | None]
    salario_max: Mapped[Decimal | None]
    vagas_total: Mapped[int | None]
    link_inscricao: Mapped[str | None]
    resumo: Mapped[str | None]
    dados: Mapped[dict[str, Any]] = mapped_column(JSONB)
    modelo: Mapped[str | None]
    criado_em: Mapped[datetime] = mapped_column(server_default="now()")

    publicacao: Mapped[Publicacao] = relationship()
    cargos: Mapped[list["Cargo"]] = relationship(back_populates="edital", cascade="all, delete-orphan")


class Cargo(Base):
    __tablename__ = "cargos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id"))
    nome: Mapped[str]
    escolaridade: Mapped[str]
    vagas: Mapped[int | None]
    cadastro_reserva: Mapped[bool] = mapped_column(server_default="false")
    salario: Mapped[Decimal | None]

    edital: Mapped[Edital] = relationship(back_populates="cargos")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    nome: Mapped[str | None]
    email: Mapped[str | None]
    plano: Mapped[str] = mapped_column(server_default="free")
    ativo: Mapped[bool] = mapped_column(server_default="true")
    criado_em: Mapped[datetime] = mapped_column(server_default="now()")

    filtros: Mapped[list["Filtro"]] = relationship(back_populates="usuario")


class Filtro(Base):
    __tablename__ = "filtros"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    palavras: Mapped[str] = mapped_column(server_default="")
    ufs: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    escolaridades: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    salario_min: Mapped[Decimal | None]
    ativo: Mapped[bool] = mapped_column(server_default="true")
    criado_em: Mapped[datetime] = mapped_column(server_default="now()")

    usuario: Mapped[Usuario] = relationship(back_populates="filtros")


class Acompanhamento(Base):
    __tablename__ = "acompanhamentos"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id"), primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(server_default="now()")


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    edital_id: Mapped[int] = mapped_column(ForeignKey("editais.id"))
    motivo: Mapped[str]
    canal: Mapped[str] = mapped_column(server_default="telegram")
    status: Mapped[str] = mapped_column(server_default="pendente")
    tentativas: Mapped[int] = mapped_column(server_default="0")
    erro: Mapped[str | None]
    criado_em: Mapped[datetime] = mapped_column(server_default="now()")
    enviado_em: Mapped[datetime | None]

    usuario: Mapped[Usuario] = relationship()
    edital: Mapped[Edital] = relationship()


class Coleta(Base):
    __tablename__ = "coletas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fonte: Mapped[str]
    data_ref: Mapped[date]
    iniciada_em: Mapped[datetime] = mapped_column(server_default="now()")
    finalizada_em: Mapped[datetime | None]
    itens_lidos: Mapped[int] = mapped_column(server_default="0")
    itens_novos: Mapped[int] = mapped_column(server_default="0")
    erro: Mapped[str | None]
