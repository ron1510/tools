from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ErrorStage = Literal["parse", "transform", "compile", "semantic"]


class OpiumSourceSpan(BaseModel):
    """Best-effort source location for diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None


class OpiumErrorDetail(BaseModel):
    """Structured diagnostic payload carried by every project error."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    stage: ErrorStage
    message: str
    hint: str | None = None
    span: OpiumSourceSpan | None = None
    expected: tuple[str, ...] = Field(default_factory=tuple)
    actual: str | None = None
    context: Mapping[str, str] = Field(default_factory=dict)


class _OpiumDetailedError(Exception):
    default_code = "opium.error"
    default_stage: ErrorStage = "semantic"

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: OpiumErrorDetail | None = None,
        code: str | None = None,
        stage: ErrorStage | None = None,
        hint: str | None = None,
        span: OpiumSourceSpan | None = None,
        expected: tuple[str, ...] = (),
        actual: str | None = None,
        context: Mapping[str, str] | None = None,
    ) -> None:
        if detail is None:
            resolved_message = message or self.default_code
            detail = OpiumErrorDetail(
                code=code or self.default_code,
                stage=stage or self.default_stage,
                message=resolved_message,
                hint=hint,
                span=span,
                expected=expected,
                actual=actual,
                context=context or {},
            )
        super().__init__(detail.message)
        self.detail = detail


class OpiumParserError(_OpiumDetailedError):
    """Base class for Opium parser errors."""

    default_code = "parse.error"
    default_stage: ErrorStage = "parse"


class UnsupportedOpiumSyntaxError(OpiumParserError):
    """Raised when an expression uses syntax outside the supported Opium subset."""

    default_code = "syntax.unsupported"


class InvalidOpiumExpressionError(OpiumParserError):
    """Raised when supported syntax is semantically invalid for the parser."""

    default_code = "syntax.invalid_expression"
    default_stage: ErrorStage = "transform"


class OpiumCompilerError(_OpiumDetailedError):
    """Base class for Opium compiler errors."""

    default_code = "compile.error"
    default_stage: ErrorStage = "compile"


class UnsupportedOpiumCompilationError(OpiumCompilerError):
    """Raised when parsed Opium syntax has no supported Gremlin compilation."""

    default_code = "compile.unsupported_expression"


class InvalidOpiumSemanticError(OpiumCompilerError):
    """Raised when parsed Opium syntax is invalid for documented Opium semantics."""

    default_code = "semantic.invalid"
    default_stage: ErrorStage = "semantic"


def error_context(**items: Any) -> Mapping[str, str]:
    """Create string-only diagnostic context from simple values."""

    return {key: str(value) for key, value in items.items()}
