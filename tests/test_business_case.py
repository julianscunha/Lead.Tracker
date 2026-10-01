"""Montagem determinística do business case (T1+T2) — empresas fictícias, sem rede, sem IA."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from core.business_case import (
    AGING_CONFIRM_DAYS, AGING_STALE_DAYS, SCORE_LABELS, SEVERITY_LABELS, assemble_business_case, score_band,
)
from core.errors import DomainError, ErrorCategory
from core.models import Company, Opportunity, Product, Service, SourceRef
from core.opportunity_engine import compute_severity_band

HOJE = date(2026, 10, 1)
SYNC = datetime(2026, 9, 20, tzinfo=timezone.utc)  # 11 dias antes de HOJE


def _opp(**kw) -> Opportunity:
    base = dict(
        company_id="c1", type="cross-sell", opportunity_score=0.9, financial_potential=0.5,
        strategic_score=0.2, confidence_score=0.8,
        evidence=["Backup local instalado", "Microsoft 365 em uso"],
        justification="Há uma lacuna de proteção em nuvem.",
        sources=[SourceRef(type="salesforce"), SourceRef(type="csv")],
        synced_at=SYNC, scope_note="parcial", criticality="critico_interno",
        discovery_prompt="PERGUNTA-SECRETA-DA-TELA",
    )
    base.update(kw)
    return Opportunity(**base)


EMPRESA = Company(name="Empresa Alfa Ltda")
ITEM = Product(vendor_id="v1", name="Nuvem Segura", description="Backup gerenciado em nuvem com retenção.")


def _bc(opp=None, company=EMPRESA, item=ITEM, today=HOJE):
    return assemble_business_case(opp or _opp(), company, item, today)


def test_sem_evidencia_levanta_erro_de_dominio_em_linguagem_de_negocio():
    with pytest.raises(DomainError) as exc:
        _bc(_opp(evidence=[]))
    assert "faltam evidências para esta oportunidade" in exc.value.message
    assert exc.value.category == ErrorCategory.EXPORT


def test_evidencia_so_com_espacos_levanta_erro_export():
    with pytest.raises(DomainError) as exc:
        _bc(_opp(evidence=["  ", "\t"]))
    assert exc.value.category == ErrorCategory.EXPORT


def test_cabecalho_traz_empresa_item_e_data():
    bc = _bc()
    assert bc.empresa == "Empresa Alfa Ltda"
    assert bc.item == "Nuvem Segura"
    assert bc.data == HOJE


def test_quatro_scores_separados_com_rotulos_e_faixas():
    bc = _bc()
    assert bc.scores == (
        ("Aderência ao portfólio", "Alta"),
        ("Porte estimado da conta", "Média"),
        ("Relevância estratégica", "Baixa"),
        ("Solidez das evidências", "Alta"),
    )
    assert len(SCORE_LABELS) == 4


@pytest.mark.parametrize("valor,faixa", [
    (0.0, "Baixa"), (0.33, "Baixa"), (0.34, "Média"), (0.66, "Média"), (0.67, "Alta"), (1.0, "Alta"), (None, "Não avaliado"),
])
def test_faixa_do_score_em_tercos(valor, faixa):
    assert score_band(valor) == faixa


def test_score_nan_vira_nao_avaliado():
    """Score NaN (float('nan')) deve retornar 'Não avaliado'."""
    import math
    assert score_band(math.nan) == "Não avaliado"


def test_score_none_vira_nao_avaliado_no_cabecalho():
    d = dict(_bc(_opp(financial_potential=None, strategic_score=None)).scores)
    assert d["Porte estimado da conta"] == "Não avaliado"
    assert d["Relevância estratégica"] == "Não avaliado"


def test_nao_expoe_numero_cru_nem_total_dos_scores():
    texto = _bc().texto_completo()
    for cru in ("0,9", "0.9", "0,8", "0.8", "0.5", "total", "Total"):
        assert cru not in texto


def test_legenda_diz_que_dimensoes_sao_independentes():
    assert "independentes" in _bc().legenda_scores


@pytest.mark.parametrize("scope", ["isolado", "parcial", "generalizado"])
@pytest.mark.parametrize("crit", ["nao_critico", "critico_interno", "critico_exposto"])
def test_custo_de_nao_agir_reusa_compute_severity_band(scope, crit):
    banda = compute_severity_band(scope, crit)
    bc = _bc(_opp(scope_note=scope, criticality=crit))
    assert bc.severidade == banda
    assert SEVERITY_LABELS[banda] in bc.custo


def test_severidade_nao_avaliada_mantem_secao_com_nao_avaliado():
    bc = _bc(_opp(scope_note=None, criticality=None))
    assert bc.severidade == "nao_avaliado"
    assert "Não avaliado" in bc.custo


def test_discovery_prompt_nunca_entra_no_documento():
    assert "PERGUNTA-SECRETA-DA-TELA" not in _bc().texto_completo()


def test_sem_valores_monetarios_nem_percentual_inventados():
    texto = _bc().texto_completo()
    for proibido in ("R$", "%", "mil ", "milhões", "milhao"):
        assert proibido not in texto


def test_evidencia_da_fonte_com_valores_e_percentuais_preservada_exatamente():
    """Fatos citados da fonte (R$, %) são citados como-estão; assembler não acrescenta símbolos."""
    bc = _bc(_opp(evidence=["Budget R$ 50 mil", "30% de uptime atingido"]))
    assert "Budget R$ 50 mil" in bc.situacao
    assert "30% de uptime atingido" in bc.situacao


def test_estado_futuro_usa_descricao_do_item():
    assert "Backup gerenciado em nuvem" in _bc().estado_futuro


def test_estado_futuro_sem_descricao_mostra_so_o_nome():
    bc = _bc(item=Service(name="Consultoria Beta"))
    assert bc.estado_futuro == "Consultoria Beta"
    assert "preencher" not in bc.texto_completo()


def test_estado_futuro_com_descricao_em_branco_mostra_so_o_nome():
    assert _bc(item=Service(name="Consultoria Beta", description="   ")).estado_futuro == "Consultoria Beta"


def test_estado_futuro_trunca_por_palavras_de_forma_deterministica():
    longa = " ".join(f"p{i}" for i in range(200))
    a = _bc(item=Service(name="S", description=longa)).estado_futuro
    b = _bc(item=Service(name="S", description=longa)).estado_futuro
    assert a == b
    assert a.startswith("p0 p1")
    assert a.endswith("…")
    assert len(a.split()) == 60


def test_situacao_rotula_data_de_sincronizacao():
    s = _bc().situacao
    assert "Dado sincronizado em 20/09/2026 (a data do fato no CRM pode ser anterior)" in s
    assert "Backup local instalado" in s


def test_evidencia_recente_nao_traz_aviso():
    s = _bc().situacao
    assert "confirme com o cliente" not in s
    assert "Dado antigo" not in s


def test_evidencia_acima_de_30_dias_pede_confirmacao():
    s = _bc(_opp(synced_at=datetime(2026, 8, 20, tzinfo=timezone.utc))).situacao  # 42 dias
    assert "confirme com o cliente antes de usar" in s
    assert "Dado antigo" not in s


def test_evidencia_acima_de_90_dias_destaca_dado_antigo():
    s = _bc(_opp(synced_at=datetime(2026, 6, 1, tzinfo=timezone.utc))).situacao  # 122 dias
    assert "Dado antigo (122 dias): reconfirmar" in s


@pytest.mark.parametrize("dias,esperado", [
    (30, {"sem_aviso": True, "confirme": False, "antigo": False}),
    (31, {"sem_aviso": False, "confirme": True, "antigo": False}),
    (90, {"sem_aviso": False, "confirme": True, "antigo": False}),
    (91, {"sem_aviso": False, "confirme": False, "antigo": True}),
])
def test_bordas_de_envelhecimento_de_evidencia(dias, esperado):
    from datetime import timedelta
    sync = HOJE - timedelta(days=dias)
    sync_dt = datetime(sync.year, sync.month, sync.day, tzinfo=timezone.utc)
    s = _bc(_opp(synced_at=sync_dt)).situacao

    if esperado["sem_aviso"]:
        assert "confirme com o cliente" not in s and "Dado antigo" not in s
    if esperado["confirme"]:
        assert "confirme com o cliente antes de usar" in s
    if esperado["antigo"]:
        assert f"Dado antigo ({dias} dias)" in s


def test_exatamente_30_dias_ainda_nao_avisa():
    s = _bc(_opp(synced_at=datetime(2026, 9, 1, tzinfo=timezone.utc))).situacao  # 30 dias
    assert "confirme com o cliente" not in s


def test_texto_nunca_usa_hoje_recente_atual():
    """Palavras inteiras ('hoje', 'recente', 'atual') proibidas — não substring."""
    import re
    texto = _bc().texto_completo().lower()
    for palavra in ("hoje", "recente", "atual"):
        assert not re.search(rf"\b{palavra}\b", texto), f"Palavra proibida '{palavra}' encontrada em: {texto}"


def test_confianca_baixa_liga_tom_condicional():
    assert _bc(_opp(confidence_score=0.2)).tom_condicional is True


def test_confianca_media_ou_alta_nao_liga_tom_condicional():
    assert _bc(_opp(confidence_score=0.5)).tom_condicional is False
    assert _bc(_opp(confidence_score=0.9)).tom_condicional is False


def test_confianca_nao_avaliada_nao_liga_tom_condicional():
    assert _bc(_opp(confidence_score=None)).tom_condicional is False


def test_rodape_traz_fontes_solidez_e_marca_de_rascunho():
    r = _bc().rodape
    assert "salesforce" in r and "csv" in r
    assert "Solidez das evidências: Alta" in r
    assert "rascunho para revisão do vendedor; não enviado" in r


def test_justificativa_minuscula_com_sigla_preservada():
    """Justificativa lowercase com sigla no meio ('DR') preserva maiúsculas."""
    bc = _bc(_opp(justification="Há uma lacuna de DR na nuvem."))
    assert "Os dados indicam que há uma lacuna de DR na nuvem." in bc.gap
    assert "DR" in bc.gap


def test_justificativa_comeca_com_sigla_preserva_maiucula():
    """Justificativa começando com sigla ('VDC365') mantém sigla maiúscula."""
    bc = _bc(_opp(justification="VDC365 ausente em produção."))
    assert "Os dados indicam que VDC365 ausente em produção." in bc.gap
    assert "VDC365" in bc.gap


def test_confianca_baixa_usa_sugere_na_justificativa():
    """Confiança baixa → 'sugere' em vez de 'indica' na justificativa."""
    bc = _bc(_opp(confidence_score=0.2, justification="Há uma lacuna."))
    assert "Os dados sugerem que há uma lacuna." in bc.gap
    assert "indicam" not in bc.gap


def test_gap_traz_motivo_e_ate_tres_evidencias():
    bc = _bc(_opp(evidence=["e1", "e2", "e3", "e4", "e5"]))
    assert "há uma lacuna de proteção em nuvem." in bc.gap
    assert "e3" in bc.gap and "e4" not in bc.gap


def test_gap_sem_justificativa_mostra_so_o_fato():
    assert "Backup local instalado" in _bc(_opp(justification=None)).gap


@pytest.mark.parametrize("campo,limite", [("situacao", 70), ("gap", 70), ("custo", 60), ("estado_futuro", 60), ("rodape", 40)])
def test_limite_de_palavras_por_secao(campo, limite):
    longo = " ".join(f"palavra{i}" for i in range(300))
    bc = _bc(
        _opp(evidence=[longo] * 6, justification=longo, sources=[SourceRef(type=f"fonte{i}") for i in range(60)]),
        item=Product(vendor_id="v", name="N", description=longo),
    )
    assert len(getattr(bc, campo).split()) <= limite


def test_nao_altera_a_oportunidade_de_entrada():
    opp = _opp()
    antes = opp.model_dump()
    _bc(opp)
    assert opp.model_dump() == antes
