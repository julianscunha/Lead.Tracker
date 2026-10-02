"""
Registro de fontes de dado configuráveis pela tela de Configurações.

Cada fonte é um dado (`SourceDescriptor`), não código — a UI e as rotas
nunca fazem `if source_id == "salesforce"`; tudo vem daqui. Adicionar uma
fonte nova (Website, Google Maps, quando os providers existirem) é só
acrescentar um descritor, nunca lógica nova de tela/rota
(docs/implementacao/specs/fase0-configuracoes-fontes.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from providers.base import DataProvider
from providers.enrichment_http import EnrichmentHttpProvider
from providers.google_maps import GoogleMapsProvider
from providers.salesforce import SalesforceProvider
from providers.website import WebsiteProvider


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
        implemented=True,
        fields=[
            SourceField(
                key="COMPANY_WEBSITE",
                label="Endereço do site da sua empresa",
                help_text=(
                    "Usado para sugerir o portfólio a partir do seu site (você revisa antes de valer). "
                    "Só lemos este endereço; informe o site completo, ex.: https://minhaempresa.com.br."
                ),
            ),
        ],
        build=lambda env: WebsiteProvider(env.get("COMPANY_WEBSITE", "")),
    ),
    SourceDescriptor(
        id="enrichment",
        label="Enriquecimento de empresas (porte e setor)",
        enabled_key="ENRICHMENT_ENABLED",
        implemented=True,
        fields=[
            SourceField(
                key="ENRICHMENT_URL_TEMPLATE",
                label="Endereço da API (com {domain})",
                help_text=(
                    "Endereço da API de dados de empresas que você contratou, com {domain} no lugar do site da empresa. "
                    "Ex.: https://api.exemplo.com/v1/companies?domain={domain}. A API deve responder JSON."
                ),
            ),
            SourceField(
                key="ENRICHMENT_AUTH_HEADER",
                label="Nome do cabeçalho de autenticação",
                help_text="Cabeçalho onde a chave é enviada. Ex.: Authorization ou X-Api-Key. Deixe vazio se a API não pede chave.",
            ),
            SourceField(
                key="ENRICHMENT_API_KEY",
                label="Chave da API",
                help_text="Enviada só em https e só no cabeçalho acima. Se a API pede um prefixo, inclua-o. Ex.: Bearer abc123.",
                secret=True,
            ),
            SourceField(
                key="ENRICHMENT_MAP_EMPLOYEES",
                label="Onde está o número de funcionários na resposta",
                help_text="Caminho com pontos dentro do JSON. Ex.: metrics.employees. Só números exatos valem; faixas (51-200) são ignoradas.",
            ),
            SourceField(
                key="ENRICHMENT_MAP_INDUSTRY",
                label="Onde está o setor na resposta",
                help_text="Caminho com pontos dentro do JSON. Ex.: category.industry.",
            ),
        ],
        # Não participa do /sync: só o botão "Completar porte e setor" (Entrada de dados) a usa.
        build=lambda env: EnrichmentHttpProvider.from_env(env),
    ),
    SourceDescriptor(
        id="google_maps",
        label="Google Maps",
        enabled_key="GOOGLE_MAPS_ENABLED",
        implemented=True,
        fields=[
            SourceField(
                key="GOOGLE_MAPS_API_KEY",
                label="Chave de API do Google Maps",
                help_text=(
                    "Usada para prospecção geográfica. Para obter: crie um projeto em "
                    "console.cloud.google.com, habilite a Geocoding API e a Places API (New), "
                    "depois gere a chave em \"APIs e Serviços → Credenciais\"."
                ),
                secret=True,
            ),
        ],
        # GoogleMapsProvider.fetch_companies() devolve [] de propósito — não
        # participa do /sync periódico (ver providers/google_maps.py). O
        # test_connection real da chave acontece via .discover()/geocode,
        # exercitado pela tela de Configurações (botão "Testar conexão").
        build=lambda env: GoogleMapsProvider(env.get("GOOGLE_MAPS_API_KEY", "")),
    ),
]


def get_source(source_id: str) -> SourceDescriptor | None:
    return next((s for s in SOURCES if s.id == source_id), None)
