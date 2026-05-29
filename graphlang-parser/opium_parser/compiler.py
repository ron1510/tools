from __future__ import annotations

from opium_parser.ast_nodes import (
    BinaryOpExpr,
    BooleanExpr,
    CallExpr,
    Expr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NumberExpr,
    Query,
    StringExpr,
    SubscriptExpr,
)
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    UnsupportedOpiumCompilationError,
)
from opium_parser.gremlin_ir import GremlinTraversal
from opium_parser.gremlin_renderer import (
    quote_groovy,
    render_label_args,
    render_literal,
    render_predicate,
    render_within,
)
from opium_parser.parser import parse_opium


def compile_opium_to_gremlin(source: str) -> str:
    return compile_ast_to_gremlin(parse_opium(source))


def compile_ast_to_gremlin(query: Query) -> str:
    return _Compiler().compile_query(query)


class _Compiler:
    def compile_query(self, query: Query) -> str:
        return self._compile_traversal(query.root, child=False).render()

    def _compile_traversal(self, expr: Expr, *, child: bool) -> GremlinTraversal:
        if isinstance(expr, CallExpr):
            return self._compile_call(expr, child=child)
        if isinstance(expr, MethodCallExpr):
            traversal = self._compile_traversal(expr.receiver, child=child)
            self._apply_method(traversal, expr)
            return traversal
        if isinstance(expr, SubscriptExpr):
            traversal = self._compile_traversal(expr.receiver, child=child)
            traversal.add(_compile_projection_step(expr.field))
            return traversal

        msg = f"Cannot compile {type(expr).__name__} as a Gremlin traversal"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_call(self, call: CallExpr, *, child: bool) -> GremlinTraversal:
        if call.function == "get":
            if child:
                msg = "get(...) is only supported as a root traversal for now"
                raise UnsupportedOpiumCompilationError(msg)
            labels = _string_args(call)
            if not labels:
                msg = "get(...) requires at least one resource"
                raise InvalidOpiumSemanticError(msg)
            traversal = GremlinTraversal("g.V()")
            traversal.add(f".hasLabel({render_label_args(labels)})")
            if "_key" in call.kwargs:
                traversal.add(_compile_key_filter(call.kwargs["_key"]))
            _reject_unknown_kwargs(call, {"_key"})
            return traversal

        if call.function in {"traverse", "traverse_any", "traverse_out", "traverse_in"}:
            traversal = GremlinTraversal("__" if child else "g.V()")
            self._apply_traverse(traversal, call)
            return traversal

        if call.function == "into":
            traversal = GremlinTraversal("__" if child else "g.E()")
            self._apply_into(traversal, call)
            return traversal

        if call.function == "var":
            name = _single_string_arg(call, "var")
            return GremlinTraversal(f"select({quote_groovy(name)})")

        msg = f"{call.function}(...) cannot start a Gremlin traversal"
        raise UnsupportedOpiumCompilationError(msg)

    def _apply_method(self, traversal: GremlinTraversal, call: MethodCallExpr) -> None:
        method = call.method

        if method in {"traverse", "traverse_any", "traverse_out", "traverse_in"}:
            self._apply_traverse(traversal, call)
        elif method == "into":
            self._apply_into(traversal, call)
        elif method == "skip":
            traversal.add(f".skip({_single_int_arg(call, 'skip')})")
        elif method == "limit":
            traversal.add(f".limit({_single_int_arg(call, 'limit')})")
        elif method == "count":
            _expect_no_args(call)
            traversal.add(".count()")
        elif method == "unique":
            _expect_no_args(call)
            traversal.add(".dedup()")
        elif method == "as_var":
            traversal.add(f".as({quote_groovy(_single_string_arg(call, 'as_var'))})")
        elif method in {"match", "match_all", "match_any"}:
            self._apply_match(traversal, call)
        elif method == "array":
            subquery = _single_expr_arg(call, "array")
            child = self._compile_traversal(subquery, child=True).render()
            traversal.add(f".local({child}).fold()")
        elif method == "flatten":
            depth = _optional_int_kwarg(call, "depth", default=1)
            _reject_positional(call, "flatten")
            traversal.extend([".unfold()" for _ in range(depth)])
        elif method == "assign":
            self._apply_assign(traversal, call)
        elif method == "select":
            self._apply_select(traversal, call)
        else:
            msg = f"Unsupported method for Gremlin compilation: {method}"
            raise UnsupportedOpiumCompilationError(msg)

    def _apply_traverse(
        self, traversal: GremlinTraversal, call: CallExpr | MethodCallExpr
    ) -> None:
        labels = _string_args(call)
        direction = _direction(call)
        min_depth = _optional_int_kwarg(call, "min_depth", default=1)
        max_depth = _optional_int_kwarg(call, "max_depth", default=1)
        _reject_unknown_kwargs(call, {"min_depth", "max_depth", "direction"})

        if min_depth != 1 or max_depth != 1:
            msg = "Traversal depth other than 1 is not compiled yet"
            raise UnsupportedOpiumCompilationError(msg)

        step = {"any": "bothE", "outbound": "outE", "inbound": "inE"}[direction]
        traversal.add(f".{step}({render_label_args(labels)})")

    def _apply_into(
        self, traversal: GremlinTraversal, call: CallExpr | MethodCallExpr
    ) -> None:
        _reject_unknown_kwargs(call, set())
        labels = _string_args(call)
        traversal.add(".otherV()")
        if labels:
            traversal.add(f".hasLabel({render_label_args(labels)})")

    def _apply_match(self, traversal: GremlinTraversal, call: MethodCallExpr) -> None:
        conditions = [
            *_keyword_conditions(call.kwargs),
            *(self._compile_condition(arg) for arg in call.args),
        ]
        if not conditions:
            return

        if call.method in {"match", "match_all"}:
            traversal.extend(conditions)
            return

        anonymous = [f"__{condition}" for condition in conditions]
        traversal.add(f".or({', '.join(anonymous)})")

    def _apply_assign(self, traversal: GremlinTraversal, call: MethodCallExpr) -> None:
        if len(call.args) != 2 or call.kwargs:
            msg = "assign(...) expects (sub_query, var_name)"
            raise InvalidOpiumSemanticError(msg)
        subquery, var_name_expr = call.args
        if not isinstance(var_name_expr, StringExpr):
            msg = "assign(...) var_name must be a string literal"
            raise InvalidOpiumSemanticError(msg)
        child = self._compile_traversal(subquery, child=True).render()
        traversal.add(
            f".sideEffect({child}.fold().as({quote_groovy(var_name_expr.value)}))"
        )

    def _apply_select(self, traversal: GremlinTraversal, call: MethodCallExpr) -> None:
        columns = [_expect_string(arg, "select column") for arg in call.args]
        computed = list(call.kwargs.items())
        if not columns and not computed:
            msg = "select(...) requires at least one column"
            raise InvalidOpiumSemanticError(msg)

        names = [*columns, *(name for name, _expr in computed)]
        traversal.add(f".project({render_label_args(names)})")

        for column in columns:
            traversal.add(f".by({_compile_by_projection(column)})")
        for _name, expr in computed:
            traversal.add(f".by({self._compile_projection_expr(expr)})")

    def _compile_projection_expr(self, expr: Expr) -> str:
        if isinstance(expr, CallExpr) and expr.function == "var":
            return f"select({quote_groovy(_single_string_arg(expr, 'var'))})"
        if isinstance(expr, SubscriptExpr):
            base = self._compile_projection_expr(expr.receiver)
            return f"{base}{_compile_projection_step(expr.field)}"
        if isinstance(expr, StringExpr):
            return quote_groovy(expr.value)

        msg = f"Unsupported select projection: {type(expr).__name__}"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_condition(self, expr: Expr) -> str:
        if isinstance(expr, CallExpr):
            return self._compile_condition_call(expr)
        if isinstance(expr, BinaryOpExpr):
            field = _field_name(expr.left)
            return _compile_binary_condition(field, expr)

        msg = f"Unsupported match condition: {type(expr).__name__}"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_condition_call(self, call: CallExpr) -> str:
        if call.function in {"match", "match_all", "match_any"}:
            conditions = [
                *_keyword_conditions(call.kwargs),
                *(self._compile_condition(arg) for arg in call.args),
            ]
            if call.function == "match_any":
                return f".or({', '.join(f'__{condition}' for condition in conditions)})"
            return "".join(conditions)

        if call.function == "eq":
            field, value = _field_value_args(call)
            if field == "_key":
                return _compile_key_filter(value)
            return f".has({quote_groovy(field)}, {render_literal(value)})"
        if call.function in {"lt", "gt", "lte", "gte"}:
            field, value = _field_value_args(call)
            predicate = render_predicate(call.function, value)
            return f".has({quote_groovy(field)}, {predicate})"
        if call.function == "ne":
            field, value = _field_value_args(call)
            if field == "_key":
                return f".not(__{_compile_key_filter(value)})"
            return f".has({quote_groovy(field)}, {render_predicate('neq', value)})"
        if call.function == "value_in":
            field, value = _field_value_args(call)
            if field == "_key":
                return _compile_key_membership(value, negate=False)
            return f".has({quote_groovy(field)}, {render_within('within', value)})"
        if call.function == "nin":
            field, value = _field_value_args(call)
            if field == "_key":
                return _compile_key_membership(value, negate=True)
            return f".has({quote_groovy(field)}, {render_within('without', value)})"
        if call.function == "is_null":
            field = _single_field_arg(call, "is_null")
            return f".not(__.has({quote_groovy(field)}))"
        if call.function == "regex_matches":
            return self._compile_regex(call)

        msg = f"Unsupported condition function: {call.function}"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_regex(self, call: CallExpr) -> str:
        if len(call.args) != 2:
            msg = "regex_matches(...) expects field and regex positional arguments"
            raise InvalidOpiumSemanticError(msg)
        field = _field_name(call.args[0])
        regex = _expect_string(call.args[1], "regex")
        case_insensitive = False
        if "caseInsensitive" in call.kwargs:
            value = call.kwargs["caseInsensitive"]
            if not isinstance(value, BooleanExpr):
                msg = "regex_matches(..., caseInsensitive=...) must be boolean"
                raise InvalidOpiumSemanticError(msg)
            case_insensitive = value.value
        _reject_unknown_kwargs(call, {"caseInsensitive"})
        if case_insensitive and not regex.startswith("(?i)"):
            regex = f"(?i){regex}"
        return f".has({quote_groovy(field)}, TextP.regex({quote_groovy(regex)}))"


def _string_args(call: CallExpr | MethodCallExpr) -> list[str]:
    name = call.function if isinstance(call, CallExpr) else call.method
    return [_expect_string(arg, f"{name} arg") for arg in call.args]


def _compile_binary_condition(field: str, expr: BinaryOpExpr) -> str:
    if field == "_key":
        if expr.op == "==":
            return _compile_key_filter(expr.right)
        if expr.op == "!=":
            return f".not(__{_compile_key_filter(expr.right)})"
        msg = "_key only supports == and != binary comparisons"
        raise InvalidOpiumSemanticError(msg)

    if expr.op == "==":
        rendered = render_literal(expr.right)
    else:
        predicate_by_op = {
            "!=": "neq",
            "<": "lt",
            ">": "gt",
            "<=": "lte",
            ">=": "gte",
        }
        rendered = render_predicate(predicate_by_op[expr.op], expr.right)
    return f".has({quote_groovy(field)}, {rendered})"


def _expect_string(expr: Expr, label: str) -> str:
    if not isinstance(expr, StringExpr):
        msg = f"{label} must be a string literal"
        raise InvalidOpiumSemanticError(msg)
    return expr.value


def _single_string_arg(call: CallExpr | MethodCallExpr, name: str) -> str:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one string argument"
        raise InvalidOpiumSemanticError(msg)
    return _expect_string(call.args[0], name)


def _single_int_arg(call: MethodCallExpr, name: str) -> int:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one integer argument"
        raise InvalidOpiumSemanticError(msg)
    value = call.args[0]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name}(...) expects an integer argument"
        raise InvalidOpiumSemanticError(msg)
    return value.value


def _single_expr_arg(call: MethodCallExpr, name: str) -> Expr:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one argument"
        raise InvalidOpiumSemanticError(msg)
    return call.args[0]


def _optional_int_kwarg(
    call: CallExpr | MethodCallExpr, name: str, *, default: int
) -> int:
    if name not in call.kwargs:
        return default
    value = call.kwargs[name]
    if not isinstance(value, NumberExpr) or not isinstance(value.value, int):
        msg = f"{name} must be an integer"
        raise InvalidOpiumSemanticError(msg)
    return value.value


def _reject_unknown_kwargs(call: CallExpr | MethodCallExpr, allowed: set[str]) -> None:
    unknown = set(call.kwargs) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        msg = f"Unsupported keyword argument(s): {names}"
        raise InvalidOpiumSemanticError(msg)


def _reject_positional(call: MethodCallExpr, name: str) -> None:
    if call.args:
        msg = f"{name}(...) does not accept positional arguments"
        raise InvalidOpiumSemanticError(msg)


def _expect_no_args(call: MethodCallExpr) -> None:
    if call.args or call.kwargs:
        msg = f"{call.method}(...) does not accept arguments"
        raise InvalidOpiumSemanticError(msg)


def _direction(call: CallExpr | MethodCallExpr) -> str:
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
    direction = _expect_string(call.kwargs["direction"], "direction")
    if direction not in {"any", "outbound", "inbound"}:
        msg = "direction must be one of: any, outbound, inbound"
        raise InvalidOpiumSemanticError(msg)
    return direction


def _keyword_conditions(kwargs: dict[str, Expr]) -> list[str]:
    conditions = []
    for field, value in kwargs.items():
        if field == "_key":
            conditions.append(_compile_key_filter(value))
        else:
            conditions.append(f".has({quote_groovy(field)}, {render_literal(value)})")
    return conditions


def _field_value_args(call: CallExpr) -> tuple[str, Expr]:
    if len(call.args) != 2 or call.kwargs:
        msg = f"{call.function}(...) expects exactly two positional arguments"
        raise InvalidOpiumSemanticError(msg)
    return _field_name(call.args[0]), call.args[1]


def _single_field_arg(call: CallExpr, name: str) -> str:
    if len(call.args) != 1 or call.kwargs:
        msg = f"{name}(...) expects one field argument"
        raise InvalidOpiumSemanticError(msg)
    return _field_name(call.args[0])


def _field_name(expr: Expr) -> str:
    if isinstance(expr, StringExpr):
        return expr.value
    if isinstance(expr, NameExpr):
        return expr.name
    msg = "Expected a field name string or identifier"
    raise InvalidOpiumSemanticError(msg)


def _ensure_list(expr: Expr) -> ListExpr:
    if not isinstance(expr, ListExpr):
        msg = "Expected a list literal"
        raise InvalidOpiumSemanticError(msg)
    return expr


def _compile_projection_step(field: str) -> str:
    if field == "_key":
        return ".id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    return f".values({quote_groovy(field)})"


def _compile_by_projection(field: str) -> str:
    if field == "_key":
        return "__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}"
    return quote_groovy(field)


def _compile_key_filter(value: Expr) -> str:
    if not isinstance(value, StringExpr):
        msg = "_key filters require a string literal"
        raise InvalidOpiumSemanticError(msg)
    key_suffix = quote_groovy(f"/{value.value}")
    return f".hasId(TextP.endingWith({key_suffix}))"


def _compile_key_membership(value: Expr, *, negate: bool) -> str:
    items = _ensure_list(value).items
    filters = [f"__{_compile_key_filter(item)}" for item in items]
    if not filters:
        return ".not(__.identity())" if negate else ".filter(__.none())"

    joined = ", ".join(filters)
    if negate:
        return f".not(__.or({joined}))"
    return f".or({joined})"
