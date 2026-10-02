"""Business case em PDF: 1 página sempre, monocromático, sem pergunta em aberto."""
import re
import sys
import time
import zlib
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.business_case import NOT_ASSESSED, BusinessCase, assemble_business_case
from core.models import Company, Opportunity, Product, SourceRef
from exports.pdf import business_case_pdf

HOJE = date(2026, 10, 1)
GERADO = datetime(2026, 10, 1, 10, 30, tzinfo=timezone.utc)
ITEM = Product(vendor_id="v1", name="Nuvem Segura", description="Backup gerenciado em nuvem com retenção.")


def _opp(**kw) -> Opportunity:
    base = dict(
        company_id="c1", type="cross-sell", opportunity_score=0.9, financial_potential=0.5,
        strategic_score=0.2, confidence_score=0.8,
        evidence=["Backup local instalado", "Microsoft 365 em uso", "Sem réplica externa"],
        justification="Há uma lacuna de proteção em nuvem.",
        sources=[SourceRef(type="salesforce"), SourceRef(type="csv")],
        synced_at=datetime(2026, 9, 20, tzinfo=timezone.utc), scope_note="parcial",
        criticality="critico_interno", discovery_prompt="PERGUNTA-SECRETA-DA-TELA",
    )
    base.update(kw)
    return Opportunity(**base)


def _bc(company="Empresa Alfa Ltda", item=ITEM, **kw) -> BusinessCase:
    return assemble_business_case(_opp(**kw), Company(name=company), item, HOJE)


def _manual(**kw) -> BusinessCase:
    base = dict(
        empresa="Empresa Beta", item="Item", data=HOJE, scores=(("Aderência ao portfólio", "Alta"),) * 4,
        legenda_scores="Dimensões independentes: não são somadas nem combinadas.",
        situacao="s", gap="g", custo="c", estado_futuro="e", rodape="Fontes: manual.", severidade="alto",
        tom_condicional=False,
    )
    base.update(kw)
    return BusinessCase(**base)


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def _content(pdf: bytes) -> str:
    """Texto desenhado: descomprime os streams (zlib, stdlib) e junta os literais (...) Tj."""
    out = []
    # Captura até `endstream` SEM descartar \r/\n finais: se o último byte do dado comprimido for
    # 0x0d/0x0a, cortá-lo truncava o zlib (extração vazia e testes de ausência sem valor).
    # decompressobj tolera os bytes de sobra (a quebra de linha antes de `endstream`).
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            data = zlib.decompressobj().decompress(m.group(1))
        except zlib.error:
            continue
        out += re.findall(rb"\(((?:[^()\\]|\\.)*)\)\s*Tj", data)
    return b"\n".join(out).decode("latin-1")


def test_um_pagina_com_3_e_com_6_evidencias_longas():
    pdf3 = business_case_pdf(_bc(), GERADO)
    assert pdf3.startswith(b"%PDF") and _pages(pdf3) == 1
    longas = [f"Evidência {i} " + "detalhe técnico relevante " * 12 for i in range(6)]
    pdf6 = business_case_pdf(_bc(evidence=[e[:300] for e in longas]), GERADO)
    assert _pages(pdf6) == 1


def test_empresa_com_120_caracteres_continua_em_uma_pagina():
    pdf = business_case_pdf(_bc(company="Empresa Muito Comprida " * 5 + "SA"), GERADO)
    assert _pages(pdf) == 1


def _linhas(pdf: bytes) -> list[str]:
    return _content(pdf).split("\n")


def test_token_de_300_caracteres_cabe_e_quebra_por_caractere():
    pdf = business_case_pdf(_bc(evidence=["x" * 300, "ok"]), GERADO)
    assert _pages(pdf) == 1
    assert "xxxx" in _content(pdf)


def test_texto_normal_nao_parte_palavras_entre_linhas():
    txt = "Dado sincronizado com a nuvem. Sem solução de backup, perdendo valor financeiro relevante. " * 6
    pdf = business_case_pdf(_manual(situacao=txt, gap=txt, custo=txt, estado_futuro=txt), GERADO)
    linhas = _linhas(pdf)
    assert len(linhas) > 10
    for palavra in ("sincronizado", "solução", "valor"):
        assert sum(palavra in l for l in linhas) >= 6, palavra
    assert not any(l.strip() in {".", ","} for l in linhas)
    vocab = set(txt.split())
    corpo = [l for l in linhas if l.count(" ") > 5 and "Dimens" not in l]
    assert corpo and all(l.split()[0] in vocab and l.split()[-1] in vocab for l in corpo)


def test_tudo_nao_avaliado_sem_none_nem_nan():
    doc = _bc(opportunity_score=None, financial_potential=None, strategic_score=None, confidence_score=None,
              scope_note=None, criticality=None)
    assert doc.severidade == "nao_avaliado"
    txt = _content(business_case_pdf(doc, GERADO))
    assert NOT_ASSESSED in txt
    assert not re.search(r"(None|nan)", txt)


def test_caracteres_especiais_nao_derrubam():
    pdf = business_case_pdf(_bc(company="Café “Ágil” — Ltda… 🚀", evidence=["Veja https://exemplo.com/a?b=1 — “ok” … 🚀"]), GERADO)
    assert _pages(pdf) == 1


def test_texto_gigante_vira_uma_pagina_resumida_e_rapido():
    gigante = " ".join(f"palavra{i}" for i in range(4000))
    doc = _manual(situacao=gigante, gap=gigante, custo=gigante, estado_futuro=gigante)
    t0 = time.perf_counter()
    pdf = business_case_pdf(doc, GERADO)
    assert time.perf_counter() - t0 < 2
    assert _pages(pdf) == 1
    assert "Texto resumido." in _content(pdf)


def test_palavra_unica_gigante_por_secao_vira_uma_pagina_resumida():
    big = "y" * 60000
    pdf = business_case_pdf(_manual(situacao=big, gap=big, custo=big, estado_futuro=big), GERADO)
    assert _pages(pdf) == 1
    assert "Texto resumido." in _content(pdf)


def test_item_gigante_e_empresa_sem_espacos_cabem():
    assert _pages(business_case_pdf(_manual(item="Produto " * 250), GERADO)) == 1
    assert _pages(business_case_pdf(_manual(empresa="E" * 120), GERADO)) == 1


def test_rodape_longo_montado_a_mao_nao_quebra():
    rodape = "Fonte: relatório “interno” — " + "detalhe da fonte consultada " * 80
    pdf = business_case_pdf(_manual(rodape=rodape), GERADO)
    assert _pages(pdf) == 1
    assert _content(pdf)


def test_rodape_tem_marca_de_rascunho_e_aviso_de_resumo():
    txt = _content(business_case_pdf(_bc(), GERADO))
    assert "rascunho" in txt
    assert "Texto resumido." not in txt
    big = "palavra " * 3000
    assert "Texto resumido." in _content(business_case_pdf(_bc_com_rascunho(situacao=big), GERADO))


def _bc_com_rascunho(**kw) -> BusinessCase:
    doc = _bc()
    return replace(doc, **kw)


def test_corpo_e_estrutura_basicos():
    txt = _content(business_case_pdf(_bc(), GERADO))
    assert "%" not in txt
    assert not re.search(r"total", txt, re.I)
    for rotulo, _ in _bc().scores:
        assert rotulo in txt
    assert len(_bc().scores) == 4


def test_severidade_nao_avaliado_renderiza():
    doc = _manual(severidade="nao_avaliado", scores=(("Aderência ao portfólio", NOT_ASSESSED),) * 4)
    pdf = business_case_pdf(doc, GERADO)
    assert _pages(pdf) == 1 and NOT_ASSESSED in _content(pdf)


def test_quebras_de_linha_no_corpo():
    pdf = business_case_pdf(_manual(situacao="linha um\nlinha dois\n\nlinha tres"), GERADO)
    assert _pages(pdf) == 1
    assert "linha dois" in _content(pdf)


def test_um_pagina_tem_conteudo():
    assert "Empresa Alfa" in _content(business_case_pdf(_bc(), GERADO))


def test_pergunta_em_aberto_nunca_aparece():
    pdf = business_case_pdf(_bc(), GERADO)
    assert "PERGUNTA-SECRETA" not in _content(pdf) and b"PERGUNTA-SECRETA" not in pdf


def test_metadados():
    pdf = business_case_pdf(_bc(), GERADO)
    titulo = "Business case - Empresa Alfa Ltda - Nuvem Segura"
    hexa = ("﻿" + titulo).encode("utf-16-be").hex().encode()
    assert b"/Title (" + titulo.encode() + b")" in pdf or b"/Title <" + hexa in pdf.lower().replace(b"/title", b"/Title")
    assert b"/Author (Lead.Tracker)" in pdf
    assert b"/Lang (pt-BR)" in pdf


def test_nao_inventa_valor_monetario():
    doc = _bc()
    assert "R$" not in doc.texto_completo()
    assert "R$" not in _content(business_case_pdf(doc, GERADO))


def test_determinismo():
    assert business_case_pdf(_bc(), GERADO) == business_case_pdf(_bc(), GERADO)
