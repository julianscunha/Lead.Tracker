"""
Registro de fontes de dado configuráveis pela tela de Configurações.

Cada fonte é um dado (`SourceDescriptor`), não código — a UI e as rotas
nunca fazem `if source_id == "salesforce"`; tudo vem daqui. Adicionar uma
fonte nova (Website, Google Maps, quando os providers existirem) é só
acrescentar um descritor, nunca lógica nova de tela/rota
(docs/specs/fase0-configuracoes-fontes.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from providers.base import DataProvider
from providers.manual import ManualProvider
from providers.salesforce import SalesforceProvider


@dataclass
class SourceField:
    key: str
    label: str
    help_text: str
    secret: bool = False


@dataclass
class SourceDescriptor:
    id: str
    label: str
    # None = fonte sempre disponível, sem toggle (ex.: Manual) — a UI mostra
    # "Sempre disponível" em vez de um liga/desliga.
    enabled_key: str | None
    implemented: bool
    fields: list[SourceField] = field(default_factory=list)
    # Constrói o provider a partir do .env já carregado (dict[str, str]).
    # None para fontes ainda não implementadas.
    build: Callable[[dict[str, str]], DataProvider] | None = None


SOURCES: list[SourceDescriptor] = [
    SourceDescriptor(
        id="manual",
        label="Manual",
        enabled_key=None,
        implemented=True,
        fields=[],
        build=lambda env: ManualProvider(),
    ),
    SourceDescriptor(
        id="salesforce",
        label="Salesforce",
        enabled_key="SALESFORCE_ENABLED",
        implemented=True,
        fields=[
            SourceField(
                key="SALESFORCE_CLIENT_ID",
                label="Identificador do Aplicativo Conectado",
                help_text="Consumer Key do Aplicativo Conectado configurado no seu Salesforce.",
            ),
            SourceField(
                key="SALESFORCE_CLIENT_SECRET",
                label="Chave do Aplicativo Conectado",
                help_text="Consumer Secret do mesmo Aplicativo Conectado.",
                secret=True,
            ),
            SourceField(
                key="SALESFORCE_LOGIN_URL",
                label="Endereço de login do Salesforce",
                help_text="Ex.: https://minhaempresa.my.salesforce.com",
            ),
        ],
        # routes_settings.test_settings() só trata ProviderError como falha
        # amigável — SalesforceProvider.__init__ precisa continuar levantando
        # ProviderError (nunca outra exceção) para config incompleta.
        build=lambda env: SalesforceProvider(
            env.get("SALESFORCE_CLIENT_ID", ""),
            env.get("SALESFORCE_CLIENT_SECRET", ""),
            env.get("SALESFORCE_LOGIN_URL", ""),
        ),
    ),
    SourceDescriptor(
        id="website",
        label="Website da empresa",
        enabled_key="WEBSITE_ENABLED",
        implemented=False,
        fields=[
            SourceField(
                key="COMPANY_WEBSITE",
                label="Endereço do site da sua empresa",
                help_text="Usado para montar o portfólio automaticamente.",
            ),
        ],
    ),
    SourceDescriptor(
        id="google_maps",
        label="Google Maps",
        enabled_key="GOOGLE_MAPS_ENABLED",
        implemented=False,
        fields=[
            SourceField(
                key="GOOGLE_MAPS_API_KEY",
                label="Chave de API do Google Maps",
                help_text="Usada para prospecção geográfica.",
                secret=True,
            ),
        ],
    ),
]


def get_source(source_id: str) -> SourceDescriptor | None:
    return next((s for s in SOURCES if s.id == source_id), None)
