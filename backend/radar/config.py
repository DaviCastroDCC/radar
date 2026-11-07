from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://radar:radar@localhost:5432/radar"

    # Extração com IA. A chave é lida pelo SDK da Anthropic da variável ANTHROPIC_API_KEY.
    extractor_model: str = "claude-haiku-5-5"
    extractor_effort: str = "low"

    telegram_bot_token: str | None = None

    # INLABS (Imprensa Nacional) - cadastro gratuito em https://inlabs.in.gov.br
    inlabs_email: str | None = None
    inlabs_password: str | None = None
    dou_secoes: str = "DO1,DO2,DO3,DO1E,DO2E,DO3E"

    fontes: str = "dodf,dou"
    intervalo_coleta_min: int = 10
    pausa_entre_requisicoes_s: float = 0.5
    max_tentativas: int = 3

    max_filtros_free: int = 3

    # LGPD: onde a política completa está publicada e como falar com o controlador.
    url_politica_privacidade: str = "https://github.com/DaviCastroDCC/radar/blob/main/docs/PRIVACIDADE.md"
    contato_privacidade: str | None = None
    http_user_agent: str = "RadarConcursoBot/0.1"

    @property
    def lista_fontes(self) -> list[str]:
        return [f.strip() for f in self.fontes.split(",") if f.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
