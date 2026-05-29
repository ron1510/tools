class OpiumParserError(Exception):
    """Base class for Opium parser errors."""


class UnsupportedOpiumSyntaxError(OpiumParserError):
    """Raised when an expression uses syntax outside the supported Opium subset."""


class InvalidOpiumExpressionError(OpiumParserError):
    """Raised when supported syntax is semantically invalid for the parser."""


class OpiumCompilerError(Exception):
    """Base class for Opium compiler errors."""


class UnsupportedOpiumCompilationError(OpiumCompilerError):
    """Raised when parsed Opium syntax has no supported Gremlin compilation."""


class InvalidOpiumSemanticError(OpiumCompilerError):
    """Raised when parsed Opium syntax is invalid for documented Opium semantics."""
