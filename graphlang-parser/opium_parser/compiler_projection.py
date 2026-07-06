from __future__ import annotations

from opium_parser.ast_nodes import CallExpr, Expr, StringExpr, SubscriptExpr
from opium_parser.compiler_common import parse_projection_field, parse_variable_name_arg
from opium_parser.errors import UnsupportedOpiumCompilationError
from opium_parser.gremlin_renderer import quote_groovy
from opium_parser.resource_names import COLLECTION_SEPARATOR, RESOURCE_SEPARATOR


def _logical_id_projection(source: str) -> str:
    return (
        f"{source}.map{{def id=it.get(); def slash=id.indexOf('/'); "
        f"slash < 0 ? id.replace('{COLLECTION_SEPARATOR}', '{RESOURCE_SEPARATOR}') : "
        f"id.substring(0, slash).replace('{COLLECTION_SEPARATOR}', "
        f"'{RESOURCE_SEPARATOR}') + id.substring(slash)}}"
    )


def _edge_source_id_projection(source: str) -> str:
    return (
        f"{source}.map{{def s=it.get().toString(); "
        "def body=s.substring(s.lastIndexOf('[')+1, s.length()-1); "
        "def arrow=body.indexOf('->'); def label=it.get().label(); "
        "def sourcePart=body.substring(0, arrow); "
        "sourcePart.substring(0, sourcePart.length()-label.length()-1)}"
    )


def _edge_target_id_projection(source: str) -> str:
    return (
        f"{source}.map{{def s=it.get().toString(); "
        "s.substring(s.indexOf('->')+2, s.length()-1)}"
    )


def compile_edge_document_step() -> str:
    return (
        ".map{def e=it.get(); def s=e.toString(); "
        "def id=e.id().toString(); "
        "def body=s.substring(s.lastIndexOf('[')+1, s.length()-1); "
        "def arrow=body.indexOf('->'); def label=e.label(); "
        "def sourcePart=body.substring(0, arrow); "
        "def source=sourcePart.substring(0, sourcePart.length()-label.length()-1); "
        "def target=body.substring(arrow+2); "
        "def logicalId=id.replace('___', '.'); "
        "def slash=id.lastIndexOf('/'); "
        "def key=slash < 0 ? id : id.substring(slash + 1); "
        "def m=new LinkedHashMap(); "
        "m['_key']=key; m['_id']=logicalId; "
        "m['_from']=source.replace('___', '.'); "
        "m['_to']=target.replace('___', '.'); "
        "def ps=e.properties(); "
        "while(ps.hasNext()){def p=ps.next(); m[p.key()]=p.value()}; "
        "m}"
    )


def compile_vertex_document_step() -> str:
    return (
        ".map{def v=it.get(); "
        "def id=v.id().toString(); "
        "def logicalId=id.replace('___', '.'); "
        "def slash=id.lastIndexOf('/'); "
        "def key=slash < 0 ? id : id.substring(slash + 1); "
        "def m=new LinkedHashMap(); "
        "m['_key']=key; m['_id']=logicalId; "
        "def ps=v.properties(); "
        "while(ps.hasNext()){def p=ps.next(); m[p.key()]=p.value()}; "
        "m}"
    )


def compile_projection_step(field: str) -> str:
    field = str(parse_projection_field(field))
    # Opium `[]` projection returns scalar field values. This intentionally
    # differs from `select(...)`, which returns map/document-shaped rows.
    if field == "_key":
        return ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    if field == "_id":
        return _logical_id_projection(".id()")
    if field == "_from":
        return _logical_id_projection(_edge_source_id_projection(""))
    if field == "_to":
        return _logical_id_projection(_edge_target_id_projection(""))
    return f".coalesce(values({quote_groovy(field)}), constant(null))"


def compile_by_projection(field: str) -> str:
    if field == "_key":
        # Provider ids look like `collection/key`. Opium `_key` is only the key
        # suffix, so this Groovy closure strips everything through the final
        # slash. This is provider-specific and should be revisited when moving to
        # Gremlin Python bytecode.
        return "__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    if field == "_id":
        return _logical_id_projection("__.id()")
    if field == "_from":
        # The provider does not expose `_from` as a normal edge property and
        # adjacent-vertex steps fail on dangling endpoints. Parse the endpoint
        # id from the provider edge string so edge documents remain inspectable.
        return _logical_id_projection(_edge_source_id_projection("__"))
    if field == "_to":
        # Same reasoning as `_from`: parse the target id without materializing
        # the target vertex, which may not exist for dangling edges.
        return _logical_id_projection(_edge_target_id_projection("__"))
    # Missing properties are projected as explicit nulls so result maps have a
    # stable shape. Gremlin `values(field)` would otherwise drop the traverser.
    return f"coalesce(values({quote_groovy(field)}), constant(null))"


def compile_projection_expr(expr: Expr) -> str:
    """Compile expressions allowed in computed `select` columns."""

    if isinstance(expr, CallExpr) and expr.function == "var":
        return f"select({quote_groovy(parse_variable_name_arg(expr, 'var'))})"
    if isinstance(expr, SubscriptExpr):
        base = compile_projection_expr(expr.receiver)
        return f"{base}{compile_projection_step(expr.field)}"
    if isinstance(expr, StringExpr):
        return quote_groovy(expr.value)

    msg = f"Unsupported select projection: {type(expr).__name__}"
    raise UnsupportedOpiumCompilationError(
        msg,
        code="compile.unsupported_select_expression",
        actual=type(expr).__name__,
    )
