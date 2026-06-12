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
    error_context,
)
from opium_parser.gremlin_renderer import (
    quote_groovy,
    render_label_args,
    render_literal,
    render_predicate,
    render_within,
)
from opium_parser.resource_names import normalize_resource_names
from opium_parser.types import (
    DepthRange,
    FieldName,
    FlattenDepth,
    LimitCount,
    MatchOperator,
    PositiveDepth,
    ProjectionField,
    ResourceName,
    SkipCount,
    TraversalDirection,
    VariableName,
)

TRAVERSE_NAMES = frozenset({"traverse", "traverse_any", "traverse_out", "traverse_in"})


def string_args(call: CallExpr | MethodCallExpr) -> list[ResourceName]:
    name = call.function if isinstance(call, CallExpr) else call.method
    return [parse_resource_arg(arg, str(name)) for arg in call.args]


def render_resource_args(call: CallExpr | MethodCallExpr) -> str:
    return str(render_label_args(normalize_resource_names(string_args(call))))


def parse_resource_arg(expr: Expr, owner: str) -> ResourceName:
    return ResourceName(parse_string_literal(expr, f"{owner} resource"))


def parse_string_literal(expr: Expr, label: str) -> str:
    if not isinstance(expr, StringExpr):
        msg = f"{label} must be a string literal"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("string",),
            actual=type(expr).__name__,
            context=error_context(argument=label),
        )
    return expr.value


def parse_single_string_arg(call: CallExpr | MethodCallExpr, name: str) -> str:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one string argument"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("one string positional argument",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(call=name),
        )
    return parse_string_literal(call.args[0], name)


def parse_variable_name_arg(call: CallExpr | MethodCallExpr, name: str) -> VariableName:
    return VariableName(parse_single_string_arg(call, name))


def parse_single_int_arg(call: MethodCallExpr, name: str) -> int:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one integer argument"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("one integer positional argument",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(method=name),
        )
    value = call.args[0]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name}(...) expects an integer argument"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("integer",),
            actual=type(value).__name__,
            context=error_context(method=name),
        )
    return value.value


def parse_limit_count(call: MethodCallExpr) -> LimitCount:
    value = parse_single_int_arg(call, "limit")
    return LimitCount(parse_non_negative_int(value, "limit"))


def parse_skip_count(call: MethodCallExpr) -> SkipCount:
    return SkipCount(parse_non_negative_int(parse_single_int_arg(call, "skip"), "skip"))


def parse_non_negative_int(value: int, label: str) -> int:
    if value < 0:
        msg = f"{label} must be non-negative"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_value",
            expected=("non-negative integer",),
            actual=str(value),
            context=error_context(argument=label),
        )
    return value


def parse_single_expr_arg(call: MethodCallExpr, name: str) -> Expr:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one argument"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("one positional argument",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(method=name),
        )
    return call.args[0]


def parse_optional_int_kwarg(
    call: CallExpr | MethodCallExpr, name: str, *, default: int
) -> int:
    if name not in call.kwargs:
        return default
    value = call.kwargs[name]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name} must be an integer"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("integer",),
            actual=type(value).__name__,
            context=error_context(kwarg=name),
        )
    return value.value


def parse_flatten_depth(call: MethodCallExpr) -> FlattenDepth:
    depth = parse_optional_int_kwarg(call, "depth", default=1)
    return FlattenDepth(parse_non_negative_int(depth, "depth"))


def parse_depth_range(call: CallExpr | MethodCallExpr) -> DepthRange:
    min_depth = parse_positive_depth(
        parse_optional_int_kwarg(call, "min_depth", default=1),
        "min_depth",
    )
    max_depth = parse_positive_depth(
        parse_optional_int_kwarg(call, "max_depth", default=1),
        "max_depth",
    )
    if int(max_depth) < int(min_depth):
        msg = "traverse depth requires 1 <= min_depth <= max_depth"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_depth_range",
            expected=("1 <= min_depth <= max_depth",),
            actual=f"min_depth={min_depth}, max_depth={max_depth}",
        )
    return DepthRange(min_depth=min_depth, max_depth=max_depth)


def parse_positive_depth(value: int, label: str) -> PositiveDepth:
    if value < 1:
        msg = f"{label} must be at least 1"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_depth_range",
            expected=("positive integer",),
            actual=str(value),
            context=error_context(argument=label),
        )
    return PositiveDepth(value)


def parse_supported_kwargs(
    call: CallExpr | MethodCallExpr, allowed: set[str]
) -> Mapping[str, Expr]:
    unknown = set(call.kwargs) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        msg = f"Unsupported keyword argument(s): {names}"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.unknown_kwarg",
            expected=tuple(sorted(allowed)),
            actual=names,
        )
    return call.kwargs


def parse_no_positional_args(call: MethodCallExpr, name: str) -> Mapping[str, Expr]:
    if call.args:
        msg = f"{name}(...) does not accept positional arguments"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("no positional arguments",),
            actual=str(len(call.args)),
            context=error_context(method=name),
        )
    return call.kwargs


def parse_empty_method_call(call: MethodCallExpr) -> MethodCallExpr:
    if call.args or call.kwargs:
        msg = f"{call.method}(...) does not accept arguments"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("no arguments",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(method=call.method),
        )
    return call


def direction(call: CallExpr | MethodCallExpr) -> TraversalDirection:
    name = call.function if isinstance(call, CallExpr) else call.method
    sugar = {
        "traverse_any": "any",
        "traverse_out": "outbound",
        "traverse_in": "inbound",
    }
    if name in sugar:
        return TraversalDirection(sugar[str(name)])
    if "direction" not in call.kwargs:
        return TraversalDirection("any")
    value = parse_string_literal(call.kwargs["direction"], "direction")
    if value not in {"any", "outbound", "inbound"}:
        msg = "direction must be one of: any, outbound, inbound"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_direction",
            expected=("any", "outbound", "inbound"),
            actual=value,
        )
    return TraversalDirection(value)


def parse_operand_value_args(call: CallExpr) -> tuple[Expr, Expr]:
    if len(call.args) != 2 or call.kwargs:
        msg = f"{call.function}(...) expects exactly two positional arguments"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("two positional arguments",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(function=call.function),
        )
    return call.args[0], call.args[1]


def parse_single_field_arg(call: CallExpr, name: str) -> FieldName:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one field argument"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("one field argument",),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context=error_context(function=name),
        )
    return parse_field_name(call.args[0])


def parse_field_name(expr: Expr) -> FieldName:
    if isinstance(expr, StringExpr):
        return FieldName(expr.value)
    if isinstance(expr, NameExpr):
        return FieldName(expr.name)
    msg = "Expected a field name string or identifier"
    raise InvalidOpiumSemanticError(
        msg,
        code="semantic.invalid_argument_type",
        expected=("field name string", "field identifier"),
        actual=type(expr).__name__,
    )


def parse_projection_field(field: str) -> ProjectionField:
    return ProjectionField(field)


def is_field_expr(expr: Expr) -> bool:
    return isinstance(expr, StringExpr | NameExpr)


def parse_list_literal(expr: Expr) -> ListExpr:
    if not isinstance(expr, ListExpr):
        msg = "Expected a list literal"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("list",),
            actual=type(expr).__name__,
        )
    return expr


def parse_match_operator(op: str) -> MatchOperator:
    if op not in {"eq", "ne", "lt", "gt", "lte", "gte", "value_in", "nin"}:
        msg = f"Unsupported condition operator: {op}"
        raise UnsupportedOpiumCompilationError(
            msg,
            code="compile.unsupported_expression",
            expected=("eq", "ne", "lt", "gt", "lte", "gte", "value_in", "nin"),
            actual=op,
        )
    return MatchOperator(op)


def compile_field_condition(field: str, op: str, value: Expr) -> str:
    op = str(parse_match_operator(op))
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
            raise InvalidOpiumSemanticError(
                msg,
                code="semantic.unsupported_key_comparison",
                expected=("eq", "ne", "value_in", "nin"),
                actual=op,
                context=error_context(field=field),
            )
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
    raise UnsupportedOpiumCompilationError(
        msg,
        code="compile.unsupported_expression",
        actual=op,
    )


def compile_null_condition(field: str) -> str:
    quoted = quote_groovy(field)
    return f".or(__.not(__.has({quoted})), __.has({quoted}, null))"


def compile_key_filter(value: Expr) -> str:
    if not isinstance(value, StringExpr):
        msg = "_key filters require a string literal"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("string",),
            actual=type(value).__name__,
            context=error_context(field="_key"),
        )
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
    labels = render_resource_args(call)
    value = direction(call)
    if value == "outbound":
        return f"outE({labels}).as('opium_edge').inV()"
    if value == "inbound":
        return f"inE({labels}).as('opium_edge').outV()"
    return f"bothE({labels}).as('opium_edge').otherV()"
