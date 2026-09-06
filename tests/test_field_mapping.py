"""Testes de core/field_mapping.py — função pura, sem sessão/rede."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.field_mapping import detect_broken_mappings, split_custom_fields
from core.models import FieldMapping, SemanticFieldRole


def _mapping(api_name: str, role: SemanticFieldRole, provider_id: str = "salesforce") -> FieldMapping:
    return FieldMapping(
        provider_id=provider_id, source_field_api_name=api_name,
        source_field_label=api_name, role=role,
    )


def test_split_writes_industry_hint_to_industry_column():
    updates, remaining = split_custom_fields(
        {"Segmento__c": "Varejo"}, [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)],
    )
    assert updates == {"industry": "Varejo"}
    assert remaining == {}


def test_split_parses_iso_date_string_for_renewal_date():
    updates, _ = split_custom_fields(
        {"Data_Renovacao__c": "2026-12-01"}, [_mapping("Data_Renovacao__c", SemanticFieldRole.RENEWAL_DATE)],
    )
    assert updates["renewal_date"].year == 2026
    assert updates["renewal_date"].month == 12
    assert updates["renewal_date"].tzinfo is not None


def test_split_parses_salesforce_datetime_field_with_offset_for_renewal_date():
    """Campo Date do Salesforce vem "YYYY-MM-DD"; campo DateTime vem com
    hora+offset ("...T00:00:00.000+0000") — os dois formatos reais que
    `SalesforceProvider.fetch_context()` pode devolver precisam parsear."""
    updates, _ = split_custom_fields(
        {"Data_Renovacao__c": "2026-12-01T00:00:00.000+0000"},
        [_mapping("Data_Renovacao__c", SemanticFieldRole.RENEWAL_DATE)],
    )
    assert updates["renewal_date"].year == 2026
    assert updates["renewal_date"].month == 12
    assert updates["renewal_date"].tzinfo is not None


def test_split_parses_numeric_currency_for_deal_size_hint():
    updates, _ = split_custom_fields(
        {"Valor_Estimado__c": 75000}, [_mapping("Valor_Estimado__c", SemanticFieldRole.DEAL_SIZE_HINT)],
    )
    assert updates["deal_size_hint"] == 75000.0


def test_split_parses_numeric_string_for_deal_size_hint():
    updates, _ = split_custom_fields(
        {"Valor_Estimado__c": "75000.5"}, [_mapping("Valor_Estimado__c", SemanticFieldRole.DEAL_SIZE_HINT)],
    )
    assert updates["deal_size_hint"] == 75000.5


def test_split_rejects_boolean_as_deal_size_hint_even_though_bool_is_int_subclass():
    updates, remaining = split_custom_fields(
        {"Ativo__c": True}, [_mapping("Ativo__c", SemanticFieldRole.DEAL_SIZE_HINT)],
    )
    assert "deal_size_hint" not in updates
    assert "Ativo__c" not in remaining  # campo mapeado some do bruto mesmo com valor inválido


def test_split_unparseable_date_never_raises_and_field_removed_from_remaining():
    updates, remaining = split_custom_fields(
        {"Data_Renovacao__c": "não é uma data"}, [_mapping("Data_Renovacao__c", SemanticFieldRole.RENEWAL_DATE)],
    )
    assert "renewal_date" not in updates
    assert "Data_Renovacao__c" not in remaining


def test_split_unparseable_number_never_raises():
    updates, _ = split_custom_fields(
        {"Valor_Estimado__c": "não é número"}, [_mapping("Valor_Estimado__c", SemanticFieldRole.DEAL_SIZE_HINT)],
    )
    assert "deal_size_hint" not in updates


def test_split_empty_industry_string_never_writes_blank_value():
    updates, remaining = split_custom_fields(
        {"Segmento__c": ""}, [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)],
    )
    assert "industry" not in updates
    assert "Segmento__c" not in remaining


def test_split_null_value_never_writes_and_field_still_removed_from_remaining():
    updates, remaining = split_custom_fields(
        {"Segmento__c": None}, [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)],
    )
    assert updates == {}
    assert remaining == {}


def test_split_unmapped_fields_stay_in_remaining_raw_context():
    updates, remaining = split_custom_fields(
        {"Segmento__c": "Varejo", "Observacao__c": "texto livre qualquer"},
        [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)],
    )
    assert updates == {"industry": "Varejo"}
    assert remaining == {"Observacao__c": "texto livre qualquer"}


def test_split_mapping_for_field_not_present_in_custom_fields_is_ignored():
    updates, remaining = split_custom_fields(
        {"Outro__c": "valor"}, [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)],
    )
    assert updates == {}
    assert remaining == {"Outro__c": "valor"}


def test_split_no_mappings_leaves_everything_as_raw_context():
    updates, remaining = split_custom_fields({"A__c": "x", "B__c": "y"}, [])
    assert updates == {}
    assert remaining == {"A__c": "x", "B__c": "y"}


def test_split_multiple_roles_at_once():
    updates, remaining = split_custom_fields(
        {"Segmento__c": "Varejo", "Data_Renovacao__c": "2026-12-01", "Valor_Estimado__c": 1000.0, "Obs__c": "livre"},
        [
            _mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT),
            _mapping("Data_Renovacao__c", SemanticFieldRole.RENEWAL_DATE),
            _mapping("Valor_Estimado__c", SemanticFieldRole.DEAL_SIZE_HINT),
        ],
    )
    assert set(updates.keys()) == {"industry", "renewal_date", "deal_size_hint"}
    assert remaining == {"Obs__c": "livre"}


def test_detect_broken_mappings_flags_field_missing_from_catalog():
    broken = detect_broken_mappings(
        [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)], catalog_field_names=set(),
    )
    assert len(broken) == 1
    assert broken[0].source_field_api_name == "Segmento__c"
    assert "removido ou renomeado" in broken[0].business_message()
    assert "Segmento__c" not in broken[0].business_message()  # nunca mostra nome técnico ao usuário


def test_detect_broken_mappings_never_flags_field_present_in_catalog():
    broken = detect_broken_mappings(
        [_mapping("Segmento__c", SemanticFieldRole.INDUSTRY_HINT)], catalog_field_names={"Segmento__c"},
    )
    assert broken == []


def test_detect_broken_mappings_no_mappings_is_empty():
    assert detect_broken_mappings([], catalog_field_names=set()) == []


def test_detect_broken_mappings_business_message_names_the_role_never_the_api_field():
    broken = detect_broken_mappings(
        [_mapping("Valor_Estimado__c", SemanticFieldRole.DEAL_SIZE_HINT)], catalog_field_names=set(),
    )
    assert "Porte estimado do negócio" in broken[0].business_message()


if __name__ == "__main__":
    test_split_writes_industry_hint_to_industry_column()
    test_split_parses_iso_date_string_for_renewal_date()
    test_split_parses_salesforce_datetime_field_with_offset_for_renewal_date()
    test_split_parses_numeric_currency_for_deal_size_hint()
    test_split_parses_numeric_string_for_deal_size_hint()
    test_split_rejects_boolean_as_deal_size_hint_even_though_bool_is_int_subclass()
    test_split_unparseable_date_never_raises_and_field_removed_from_remaining()
    test_split_unparseable_number_never_raises()
    test_split_empty_industry_string_never_writes_blank_value()
    test_split_null_value_never_writes_and_field_still_removed_from_remaining()
    test_split_unmapped_fields_stay_in_remaining_raw_context()
    test_split_mapping_for_field_not_present_in_custom_fields_is_ignored()
    test_split_no_mappings_leaves_everything_as_raw_context()
    test_split_multiple_roles_at_once()
    test_detect_broken_mappings_flags_field_missing_from_catalog()
    test_detect_broken_mappings_never_flags_field_present_in_catalog()
    test_detect_broken_mappings_no_mappings_is_empty()
    test_detect_broken_mappings_business_message_names_the_role_never_the_api_field()
    print("OK — todos os testes de divisão de campo mapeado passaram")
