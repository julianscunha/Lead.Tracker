"""Smoke tests da taxonomia de erro de domínio."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.base import AIProviderError
from core.errors import DomainError, ErrorCategory
from providers.base import ProviderError


def test_domain_error_message_never_includes_technical_exception_text():
    original = ValueError("requests.exceptions.ConnectionError: raw technical detail")
    try:
        raise DomainError(ErrorCategory.CONNECTIVITY, "Não foi possível conectar.", "Verifique a internet.") from original
    except DomainError as exc:
        assert "ConnectionError" not in str(exc)
        assert "Não foi possível conectar." in str(exc)
        assert "Verifique a internet." in str(exc)


def test_ai_provider_error_is_a_domain_error_default_category_ai():
    exc = AIProviderError("falhou")
    assert isinstance(exc, DomainError)
    assert exc.category == ErrorCategory.AI


def test_ai_provider_error_accepts_explicit_category():
    exc = AIProviderError("sem credencial", category=ErrorCategory.AUTHENTICATION)
    assert exc.category == ErrorCategory.AUTHENTICATION


def test_provider_error_is_a_domain_error_default_category_integration():
    exc = ProviderError("falhou")
    assert isinstance(exc, DomainError)
    assert exc.category == ErrorCategory.INTEGRATION


if __name__ == "__main__":
    test_domain_error_message_never_includes_technical_exception_text()
    test_ai_provider_error_is_a_domain_error_default_category_ai()
    test_ai_provider_error_accepts_explicit_category()
    test_provider_error_is_a_domain_error_default_category_integration()
    print("OK — todos os testes de taxonomia de erro passaram")
