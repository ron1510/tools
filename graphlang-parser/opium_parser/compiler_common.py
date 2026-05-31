from __future__ import annotations

from collections.abc import Mapping

from opium_parser.ast_nodes import (
    CallExpr,
    Expr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NumberExpr,
    StringExpr,
)
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumCompilationError,
)
from opium_parser.gremlin_renderer import (
    quote_groovy,
    render_label_args,
    render_literal,
    render_predicate,
    render_within,
)

TRAVERSE_NAMES = frozenset({"traverse", "traverse_any", "traverse_out", "traverse_in"})


def string_args(call: CallExpr | MethodCallExpr) -> list[str]:
    name = call.function if isinstance(call, CallExpr) else call.method
    return [parse_string_literal(arg, f"{name} arg") for arg in call.args]


def parse_string_literal(expr: Expr, label: str) -> str:
    if not isinstance(expr, StringExpr):
        msg = f"{label} must be a string literal"
        raise InvalidOpiumSemanticError(msg)
    return expr.value


def parse_single_string_arg(call: CallExpr | MethodCallExpr, name: str) -> str:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one string argument"
        raise InvalidOpiumSemanticError(msg)
    return parse_string_literal(call.args[0], name)


def parse_single_int_arg(call: MethodCallExpr, name: str) -> int:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one integer argument"
        raise InvalidOpiumSemanticError(msg)
    value = call.args[0]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name}(...) expects an integer argument"
        raise InvalidOpiumSemanticError(msg)
    return value.value


def parse_single_expr_arg(call: MethodCallExpr, name: str) -> Expr:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one argument"
        raise InvalidOpiumSemanticError(msg)
    return call.args[0]


def parse_optional_int_kwarg(
    call: CallExpr | MethodCallExpr, name: str, *, default: int
) -> int:
    if name not in call.kwargs:
        return default
    value = call.kwargs[name]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name} must be an integer"
        raise InvalidOpiumSemanticError(msg)
    return value.value


def parse_supported_kwargs(
    call: CallExpr | MethodCallExpr, allowed: set[str]
) -> Mapping[str, Expr]:
    unknown = set(call.kwargs) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        msg = f"Unsupported keyword argument(s): {names}"
        raise InvalidOpiumSemanticError(msg)
    return call.kwargs


def parse_no_positional_args(call: MethodCallExpr, name: str) -> Mapping[str, Expr]:
    if call.args:
        msg = f"{name}(...) does not accept positional arguments"
        raise InvalidOpiumSemanticError(msg)
    return call.kwargs


def parse_empty_method_call(call: MethodCallExpr) -> MethodCallExpr:
    if call.args or call.kwargs:
        msg = f"{call.method}(...) does not accept arguments"
        raise InvalidOpiumSemanticError(msg)
    return call


def direction(call: CallExpr | MethodCallExpr) -> str:
    name = call.function if isinstance(call, CallExpr) else call.method
    sugar = {
        "traverse_any": "any",
        "traverse_out": "outbound",
        "traverse_in": "inbound",
    }
    if name in sugar:
        return sugar[name]
    if "direction" not in call.kwargs:
        return "any"
    value = parse_string_literal(call.kwargs["direction"], "direction")
    if value not in {"any", "outbound", "inbound"}:
        msg = "direction must be one of: any, outbound, inbound"
        raise InvalidOpiumSemanticError(msg)
    return value


def parse_operand_value_args(call: CallExpr) -> tuple[Expr, Expr]:
    if len(call.args) != 2 or call.kwargs:
        msg = f"{call.function}(...) expects exactly two positional arguments"
        raise InvalidOpiumSemanticError(msg)
    return call.args[0], call.args[1]


def parse_single_field_arg(call: CallExpr, name: str) -> str:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one field argument"
        raise InvalidOpiumSemanticError(msg)
    return parse_field_name(call.args[0])


def parse_field_name(expr: Expr) -> str:
    if isinstance(expr, StringExpr):
        return expr.value
    if isinstance(expr, NameExpr):
        return expr.name
    msg = "Expected a field name string or identifier"
    raise InvalidOpiumSemanticError(msg)


def is_field_expr(expr: Expr) -> bool:
    return isinstance(expr, StringExpr | NameExpr)


def parse_list_literal(expr: Expr) -> ListExpr:
    if not isinstance(expr, ListExpr):
        msg = "Expected a list literal"
        raise InvalidOpiumSemanticError(msg)
    return expr


def compile_field_condition(field: str, op: str, value: Expr) -> str:
    if op == "eq":
        if field == "_key":
            return compile_key_filter(value)
        return f".has({quote_groovy(field)}, {render_literal(value)})"
    if op == "ne":
        if field == "_key":
            return f".not(__{compile_key_filter(value)})"
        return f".has({quote_groovy(field)}, {render_predicate('neq', value)})"
    if op in {"lt", "gt", "lte", "gte"}:
        if field == "_key":
            msg = "_key only supports equality-style comparisons"
            raise InvalidOpiumSemanticError(msg)
        return f".has({quote_groovy(field)}, {render_predicate(op, value)})"
    if op == "value_in":
        if field == "_key":
            return compile_key_membership(value, negate=False)
        return f".has({quote_groovy(field)}, {render_within('within', value)})"
    if op == "nin":
        if field == "_key":
            return compile_key_membership(value, negate=True)
        return f".has({quote_groovy(field)}, {render_within('without', value)})"

    msg = f"Unsupported condition operator: {op}"
    raise UnsupportedOpiumCompilationError(msg)


def compile_null_condition(field: str) -> str:
    quoted = quote_groovy(field)
    return f".or(__.not(__.has({quoted})), __.has({quoted}, null))"


def compile_key_filter(value: Expr) -> str:
    if not isinstance(value, StringExpr):
        msg = "_key filters require a string literal"
        raise InvalidOpiumSemanticError(msg)
    # Because provider ids are `collection/key`, filtering by Opium `_key` uses
    # a suffix match. This assumes keys cannot contain collection separators in a
    # way that would make `/key` ambiguous.
    key_suffix = quote_groovy(f"/{value.value}")
    return f".hasId(TextP.endingWith({key_suffix}))"


def compile_key_membership(value: Expr, *, negate: bool) -> str:
    items = parse_list_literal(value).items
    filters = [f"__{compile_key_filter(item)}" for item in items]
    if not filters:
        # Empty positive membership can match nothing. Empty negative membership
        # should match everything, represented as "not impossible".
        return ".not(__.identity())" if negate else ".filter(__.none())"

    joined = ", ".join(filters)
    if negate:
        return f".not(__.or({joined}))"
    return f".or({joined})"


def deep_repeat_body(call: CallExpr | MethodCallExpr) -> str:
    labels = render_label_args(string_args(call))
    value = direction(call)
    if value == "outbound":
        return f"outE({labels}).as('opium_edge').inV()"
    if value == "inbound":
        return f"inE({labels}).as('opium_edge').outV()"
    return f"bothE({labels}).as('opium_edge').otherV()"
