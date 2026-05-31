from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from opium_parser.ast_nodes import (
    BinaryOpExpr,
    BooleanExpr,
    CallExpr,
    Expr,
    SubscriptExpr,
)
from opium_parser.compiler_common import (
    compile_field_condition,
    compile_key_filter,
    compile_null_condition,
    is_field_expr,
    parse_field_name,
    parse_operand_value_args,
    parse_single_field_arg,
    parse_string_literal,
)
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumCompilationError,
)
from opium_parser.gremlin_ir import GremlinTraversal
from opium_parser.gremlin_renderer import quote_groovy, render_literal

ConditionTraversalCompiler = Callable[[Expr], str]


def apply_match(
    traversal: GremlinTraversal,
    call_method: str,
    args: Sequence[Expr],
    kwargs: Mapping[str, Expr],
    compile_condition_operand_traversal: ConditionTraversalCompiler,
) -> None:
    conditions = [
        *keyword_conditions(kwargs),
        *(compile_condition(arg, compile_condition_operand_traversal) for arg in args),
    ]
    if not conditions:
        return

    match call_method:
        case "match" | "match_all":
            # `match` and `match_all` are currently equivalent: every condition
            # is appended as another Gremlin filter step, so they combine with
            # logical AND.
            traversal.extend(conditions)
        case "match_any":
            # Gremlin `or(...)` expects anonymous traversals. Each compiled
            # condition starts with a dot, for example `.has(...)`, so prefixing
            # `__` yields valid children such as `__.has(...)`.
            anonymous = [f"__{condition}" for condition in conditions]
            traversal.add(f".or({', '.join(anonymous)})")
        case method:
            msg = f"Unsupported match method: {method}"
            raise UnsupportedOpiumCompilationError(msg)


def keyword_conditions(kwargs: Mapping[str, Expr]) -> list[str]:
    conditions = []
    for field, value in kwargs.items():
        if field == "_key":
            conditions.append(compile_key_filter(value))
        else:
            conditions.append(f".has({quote_groovy(field)}, {render_literal(value)})")
    return conditions


def compile_condition(
    expr: Expr,
    compile_condition_operand_traversal: ConditionTraversalCompiler,
) -> str:
    if isinstance(expr, CallExpr):
        return compile_condition_call(expr, compile_condition_operand_traversal)
    if isinstance(expr, BinaryOpExpr):
        return compile_binary_condition(expr, compile_condition_operand_traversal)

    msg = f"Unsupported match condition: {type(expr).__name__}"
    raise UnsupportedOpiumCompilationError(msg)


def compile_condition_call(
    call: CallExpr,
    compile_condition_operand_traversal: ConditionTraversalCompiler,
) -> str:
    """Compile function-style match conditions."""

    match str(call.function):
        case "match" | "match_all" | "match_any":
            conditions = [
                *keyword_conditions(call.kwargs),
                *(
                    compile_condition(arg, compile_condition_operand_traversal)
                    for arg in call.args
                ),
            ]
            if call.function == "match_any":
                return f".or({', '.join(f'__{condition}' for condition in conditions)})"
            return "".join(conditions)
        case "eq":
            left, value = parse_operand_value_args(call)
            return compile_operand_condition(
                left, "eq", value, compile_condition_operand_traversal
            )
        case "lt" | "gt" | "lte" | "gte":
            left, value = parse_operand_value_args(call)
            return compile_operand_condition(
                left, call.function, value, compile_condition_operand_traversal
            )
        case "ne":
            left, value = parse_operand_value_args(call)
            return compile_operand_condition(
                left, "ne", value, compile_condition_operand_traversal
            )
        case "value_in":
            left, value = parse_operand_value_args(call)
            return compile_operand_condition(
                left, "value_in", value, compile_condition_operand_traversal
            )
        case "nin":
            left, value = parse_operand_value_args(call)
            return compile_operand_condition(
                left, "nin", value, compile_condition_operand_traversal
            )
        case "is_null":
            field = parse_single_field_arg(call, "is_null")
            return compile_null_condition(field)
        case "regex_matches":
            return compile_regex(call)
        case function:
            msg = f"Unsupported condition function: {function}"
            raise UnsupportedOpiumCompilationError(msg)


def compile_regex(call: CallExpr) -> str:
    if len(call.args) != 2:
        msg = "regex_matches(...) expects field and regex positional arguments"
        raise InvalidOpiumSemanticError(msg)
    field = parse_field_name(call.args[0])
    regex = parse_string_literal(call.args[1], "regex")
    case_insensitive = False
    if "caseInsensitive" in call.kwargs:
        value = call.kwargs["caseInsensitive"]
        if not isinstance(value, BooleanExpr):
            msg = "regex_matches(..., caseInsensitive=...) must be boolean"
            raise InvalidOpiumSemanticError(msg)
        case_insensitive = value.value
    unknown = set(call.kwargs) - {"caseInsensitive"}
    if unknown:
        names = ", ".join(sorted(unknown))
        msg = f"Unsupported keyword argument(s): {names}"
        raise InvalidOpiumSemanticError(msg)
    if case_insensitive and not regex.startswith("(?i)"):
        # Gremlin TextP.regex accepts Java regex syntax. Prefixing `(?i)` is
        # the least invasive way to implement Opium's `caseInsensitive`
        # option while leaving already-prefixed patterns unchanged.
        regex = f"(?i){regex}"
    return f".has({quote_groovy(field)}, TextP.regex({quote_groovy(regex)}))"


def compile_binary_condition(
    expr: BinaryOpExpr,
    compile_condition_operand_traversal: ConditionTraversalCompiler,
) -> str:
    op_by_symbol = {
        "==": "eq",
        "!=": "ne",
        "<": "lt",
        ">": "gt",
        "<=": "lte",
        ">=": "gte",
    }
    return compile_operand_condition(
        expr.left,
        op_by_symbol[expr.op],
        expr.right,
        compile_condition_operand_traversal,
    )


def compile_operand_condition(
    left: Expr,
    op: str,
    value: Expr,
    compile_condition_operand_traversal: ConditionTraversalCompiler,
) -> str:
    """Compile a condition whose left operand may be a field or expression."""

    if is_field_expr(left):
        return compile_field_condition(parse_field_name(left), op, value)
    if isinstance(left, SubscriptExpr):
        child = compile_condition_operand_traversal(left.receiver)
        return f".filter({child}{compile_field_condition(left.field, op, value)})"

    msg = f"Unsupported condition operand: {type(left).__name__}"
    raise UnsupportedOpiumCompilationError(msg)
