"""Smoke test do wrapper de erro de exportação."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.errors import ErrorCategory
from exports.errors import ExportError, wrap_export_errors


@wrap_export_errors
def _boom():
    raise ValueError("detalhe técnico interno da lib")


@wrap_export_errors
def _already_domain_error():
    raise ExportError("já é amigável")


def test_wrap_export_errors_converts_unexpected_exception():
    try:
        _boom()
        assert False, "deveria levantar ExportError"
    except ExportError as exc:
        assert exc.category == ErrorCategory.EXPORT
        assert "detalhe técnico interno da lib" not in str(exc)


def test_wrap_export_errors_does_not_double_wrap_domain_error():
    try:
        _already_domain_error()
        assert False, "deveria propagar o ExportError original"
    except ExportError as exc:
        assert str(exc) == "já é amigável"


if __name__ == "__main__":
    test_wrap_export_errors_converts_unexpected_exception()
    test_wrap_export_errors_does_not_double_wrap_domain_error()
    print("OK — todos os testes do wrapper de erro de exportação passaram")
