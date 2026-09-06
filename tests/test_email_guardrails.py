"""Testes de ai/email_guardrails.py — função pura, sem IA/rede real."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.email_guardrails import validate_persuasive_field


def test_empty_text_always_passes():
    assert validate_persuasive_field("", ["evid"], {}) is None
    assert validate_persuasive_field(None, ["evid"], {}) is None  # type: ignore[arg-type]


def test_plain_reformulation_of_evidence_passes():
    assert validate_persuasive_field(
        "Vocês já usam Veeam VBR sem VDC365 configurado.", ["Veeam VBR presente", "VDC365 ausente"], {},
    ) is None


def test_rejects_more_than_one_sentence():
    reason = validate_persuasive_field("Frase um. Frase dois.", [], {})
    assert reason == "mais de uma frase"


def test_decimal_point_in_number_never_counts_as_sentence_boundary():
    """Bug real encontrado durante a implementação: `4.5` tem um ponto que
    não é fim de frase — sem o fix, todo differentiator/ps com número
    decimal formatado com ponto seria rejeitado como "mais de uma frase"."""
    assert validate_persuasive_field("O ganho foi de 4.5 pontos no período.", ["ganho de 4.5 pontos"], {}) is None


def test_rejects_blocked_superlative_phrases():
    for phrase in ["líder de mercado", "comprovadamente eficaz", "100% garantido", "nunca falha"]:
        assert validate_persuasive_field(phrase, [], {}) is not None


def test_rejects_number_not_present_in_evidence_or_portfolio():
    reason = validate_persuasive_field("Isso reduz custos em 40%.", ["economia genérica"], {})
    assert reason is not None
    assert "40" in reason


def test_accepts_number_present_in_evidence():
    assert validate_persuasive_field("Isso reduz custos em 40%.", ["redução de 40% documentada"], {}) is None


def test_accepts_number_present_in_portfolio_dict_nested():
    assert validate_persuasive_field(
        "O produto custa 1500 por mês.", [], {"product": {"name": "VBR", "price": "1500"}},
    ) is None


def test_accepts_number_present_in_portfolio_as_native_int():
    """Achado de revisão de código: portfolio vindo de JSON real tem número
    nativo (int/float), não string — _flatten_strings precisa capturar isso,
    senão um differentiator citando um preço real vira falso positivo."""
    assert validate_persuasive_field("O produto custa 1500 por mês.", [], {"price": 1500}) is None
    assert validate_persuasive_field("O ganho foi de 4.5 pontos.", [], {"gain": 4.5}) is None


def test_never_treats_bool_as_matching_number():
    assert validate_persuasive_field("O produto custa 1 por mês.", [], {"active": True}) is not None


def test_never_raises_on_deeply_nested_portfolio():
    """Achado de revisão de código: portfolio anormalmente aninhado nunca
    pode estourar RecursionError e derrubar a validação inteira."""
    deep: dict = {"v": "1"}
    node = deep
    for _ in range(200):
        node["next"] = {"v": "1"}
        node = node["next"]
    result = validate_persuasive_field("Texto qualquer sem número.", [], deep)
    assert result is None or isinstance(result, str)


def test_rejects_comparative_without_anchor_number():
    reason = validate_persuasive_field("É melhor que a solução atual.", ["algo"], {})
    assert reason == "comparativo sem número âncora"


def test_comparative_with_anchor_number_from_evidence_passes():
    assert validate_persuasive_field(
        "É 30% melhor que a solução atual.", ["ganho de 30% medido"], {},
    ) is None


def test_rejects_uncited_external_source_mention():
    for phrase in ["Segundo um estudo recente", "A pesquisa mostra ganhos", "Fonte: relatório X"]:
        reason = validate_persuasive_field(phrase, [], {})
        assert reason is not None


def test_normalizes_decimal_separator_between_text_and_evidence():
    """4,5 no texto e 4.5 na evidência (ou vice-versa) são o mesmo número —
    nunca reprovar por diferença de formatação regional."""
    assert validate_persuasive_field("O ganho medido foi de 4,5% no último trimestre.", ["ganho de 4.5% medido"], {}) is None


if __name__ == "__main__":
    test_empty_text_always_passes()
    test_plain_reformulation_of_evidence_passes()
    test_rejects_more_than_one_sentence()
    test_decimal_point_in_number_never_counts_as_sentence_boundary()
    test_rejects_blocked_superlative_phrases()
    test_rejects_number_not_present_in_evidence_or_portfolio()
    test_accepts_number_present_in_evidence()
    test_accepts_number_present_in_portfolio_dict_nested()
    test_accepts_number_present_in_portfolio_as_native_int()
    test_never_treats_bool_as_matching_number()
    test_never_raises_on_deeply_nested_portfolio()
    test_rejects_comparative_without_anchor_number()
    test_comparative_with_anchor_number_from_evidence_passes()
    test_rejects_uncited_external_source_mention()
    test_normalizes_decimal_separator_between_text_and_evidence()
    print("OK — todos os testes de guard-rails de e-mail passaram")
