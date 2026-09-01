"""Erro de domínio de exportação — mesmo padrão de ProviderError/AIProviderError."""
from __future__ import annotations

import functools
from typing import Callable, TypeVar

from core.errors import DomainError, ErrorCategory

T = TypeVar("T")


class ExportError(DomainError):
    def __init__(self, message: str, recommended_action: str | None = None) -> None:
        super().__init__(ErrorCategory.EXPORT, message, recommended_action)


def wrap_export_errors(fn: Callable[..., T]) -> Callable[..., T]:
    """Rede de segurança: qualquer falha inesperada de biblioteca (fpdf2/openpyxl)
    vira ExportError amigável em vez de vazar stack trace pro chamador."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> T:
        try:
            return fn(*args, **kwargs)
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"Não foi possível gerar o arquivo de exportação ({fn.__name__}).") from exc
    return wrapper
