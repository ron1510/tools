from __future__ import annotations

from opium_parser.ast_nodes import CallExpr, Expr, StringExpr, SubscriptExpr
from opium_parser.compiler_common import parse_single_string_arg
from opium_parser.errors import UnsupportedOpiumCompilationError
from opium_parser.gremlin_renderer import quote_groovy


def compile_projection_step(field: str) -> str:
    # Subscript projection returns a one-field map, not a raw scalar. This keeps
    # `get('roles')['_key']` consistent with `select('_key')` and with the
    # project/document semantics recorded in the Opium semantics notes.
    return f".project({quote_groovy(field)}).by({compile_by_projection(field)})"


def compile_by_projection(field: str) -> str:
    if field == "_key":
        # Provider ids look like `collection/key`. Opium `_key` is only the key
        # suffix, so this Groovy closure strips everything through the final
        # slash. This is provider-specific and should be revisited when moving to
        # Gremlin Python bytecode.
        return "__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    if field == "_id":
        # Opium `_id` is the full Arango id, which the provider exposes as the
        # Gremlin element id in the tested COMPLEX setup.
        return "__.id()"
    if field == "_from":
        # The provider did not expose `_from` as a normal edge property in the
        # live lab. For edge traversers, `outV().id()` reconstructs the Arango
        # source id.
        return "__.outV().id()"
    if field == "_to":
        # Same reasoning as `_from`: reconstruct the target endpoint from the
        # edge's adjacent vertex instead of relying on `values('_to')`.
        return "__.inV().id()"
    # Missing properties are projected as explicit nulls so result maps have a
    # stable shape. Gremlin `values(field)` would otherwise drop the traverser.
    return f"coalesce(values({quote_groovy(field)}), constant(null))"


def compile_projection_expr(expr: Expr) -> str:
    """Compile expressions allowed in computed `select` columns."""

    if isinstance(expr, CallExpr) and expr.function == "var":
        return f"select({quote_groovy(parse_single_string_arg(expr, 'var'))})"
    if isinstance(expr, SubscriptExpr):
        base = compile_projection_expr(expr.receiver)
        return f"{base}{compile_projection_step(expr.field)}"
    if isinstance(expr, StringExpr):
        return quote_groovy(expr.value)

    msg = f"Unsupported select projection: {type(expr).__name__}"
    raise UnsupportedOpiumCompilationError(msg)
