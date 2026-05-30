"""Opium AST to Gremlin Groovy compiler.

This module is the semantic boundary of the project. The parser preserves what
the user wrote; the compiler decides which supported Opium expressions can be
translated into Gremlin for the current ArangoDB TinkerPop Provider setup.

Current target:

- Gremlin Groovy strings, not Gremlin Python bytecode.
- ArangoDB TinkerPop Provider in `COMPLEX` mode.
- Arango vertex and edge collections exposed as Gremlin labels.
- Arango document ids exposed by the provider as `collection/key`.

The implementation is intentionally conservative. When semantics are not clear
or not validated live, the compiler raises a custom compiler error instead of
guessing. That keeps parser coverage ahead of compiler coverage without silently
creating wrong Gremlin.
"""

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
    """Parse an Opium expression and compile it into a Gremlin Groovy string."""

    return compile_ast_to_gremlin(parse_opium(source))


def compile_ast_to_gremlin(query: Query) -> str:
    """Compile a typed Opium AST into a Gremlin Groovy string."""

    return _Compiler().compile_query(query)


class _Compiler:
    """Recursive compiler for traversal-shaped Opium expressions.

    The compiler walks from the root expression down through receivers, then
    appends Gremlin steps as it unwinds. That mirrors how a chained Opium query
    is read:

    `get('roles').traverse_out('edges').into('roles')`

    becomes:

    `g.V().hasLabel('roles').outE('edges').otherV().hasLabel('roles')`

    Child subqueries use the anonymous traversal source `__` instead of `g`.
    """

    def compile_query(self, query: Query) -> str:
        return self._compile_traversal(query.root, child=False).render()

    def _compile_traversal(self, expr: Expr, *, child: bool) -> GremlinTraversal:
        """Compile an expression that should behave as a traversal.

        `child=True` means the expression is nested inside another traversal,
        for example `array(traverse().into())`. In that mode we start from `__`
        where possible so Gremlin treats the generated traversal as local to the
        current traverser.
        """

        if isinstance(expr, CallExpr):
            return self._compile_call(expr, child=child)
        if isinstance(expr, MethodCallExpr):
            # Deep traversal followed by `into()` needs special handling because
            # the repeat body must move edge -> vertex on every hop. Compiling
            # `.traverse(max_depth=3)` first would leave the traversal on edges,
            # which is correct only when `into()` is not present.
            if expr.method == "into" and _is_deep_traverse_expr(expr.receiver):
                traversal = self._compile_traversal(
                    _traverse_receiver(expr.receiver), child=child
                )
                self._apply_deep_traverse_into(traversal, expr.receiver, expr)
                return traversal
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
        if call.function == "traverse_start":
            return GremlinTraversal("__" if child else "g.V()")

        if call.function == "get":
            if child:
                # `get(...)` inside a local child traversal would restart from
                # the whole graph rather than the current traverser. Opium may
                # eventually define that behavior, but it is not part of the
                # validated subset.
                msg = "get(...) is only supported as a root traversal for now"
                raise UnsupportedOpiumCompilationError(msg)
            labels = _string_args(call)
            if not labels:
                msg = "get(...) requires at least one resource"
                raise InvalidOpiumSemanticError(msg)
            traversal = GremlinTraversal("g.V()")
            # In the agreed Arango/Gremlin setup, Opium resource names are
            # Arango collection names and the provider exposes collections as
            # Gremlin labels. This is why `get('collection')` compiles to
            # `g.V().hasLabel('collection')`.
            traversal.add(f".hasLabel({render_label_args(labels)})")
            if "_key" in call.kwargs:
                traversal.add(_compile_key_filter(call.kwargs["_key"]))
            _reject_unknown_kwargs(call, {"_key"})
            return traversal

        if call.function in {"traverse", "traverse_any", "traverse_out", "traverse_in"}:
            # Top-level `traverse(...)` is syntactically valid Opium, but as a
            # Gremlin traversal it needs a starting point. We use `g.V()` at the
            # top level and `__` for child traversals, matching the parser's
            # policy of allowing syntax before all semantic combinations are
            # necessarily recommended.
            traversal = GremlinTraversal("__" if child else "g.V()")
            self._apply_traverse(traversal, call)
            return traversal

        if call.function == "into":
            # Standalone `into()` starts from edges. In normal use it is chained
            # after `traverse`, but accepting it here keeps the compiler behavior
            # consistent with the parser's allowed top-level call names.
            traversal = GremlinTraversal("__" if child else "g.E()")
            self._apply_into(traversal, call)
            return traversal

        if call.function == "var":
            # `var('x')` compiles to Gremlin `select('x')`. Whether a label `x`
            # is actually in scope depends on the surrounding query and is not
            # fully validated by this compiler yet.
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
            # Current interpretation: `array(subquery)` runs a local child
            # traversal for each incoming traverser and folds its results into a
            # list. This covers the simple documented shapes, but nested/scoped
            # array behavior is still marked as incomplete in docs and tests.
            subquery = _single_expr_arg(call, "array")
            child = self._compile_traversal(subquery, child=True).render()
            traversal.add(f".local({child}).fold()")
        elif method == "flatten":
            # `flatten()` is represented as one `unfold()`. `flatten(depth=N)`
            # repeats `unfold()` N times. This is a simple Gremlin mapping, not a
            # complete commitment about every nested Opium array shape.
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
            # Deep traversal has to remember the edge taken at each hop because
            # Opium `traverse(...)` returns edges, while `traverse(...).into()`
            # returns vertices. The repeat body therefore labels each edge as
            # `opium_edge` before moving to the adjacent vertex.
            traversal.add(_compile_deep_traverse_step(call, into=False))
            return

        # Default traversal returns edges. `into()` is a separate Opium step that
        # converts those edges to the opposite endpoint vertex.
        step = {"any": "bothE", "outbound": "outE", "inbound": "inE"}[direction]
        traversal.add(f".{step}({render_label_args(labels)})")

    def _apply_deep_traverse_into(
        self,
        traversal: GremlinTraversal,
        traverse_call: CallExpr | MethodCallExpr,
        into_call: MethodCallExpr,
    ) -> None:
        traversal.add(_compile_deep_traverse_step(traverse_call, into=True))
        _reject_unknown_kwargs(into_call, set())
        labels = _string_args(into_call)
        if labels:
            traversal.add(f".hasLabel({render_label_args(labels)})")

    def _apply_into(
        self, traversal: GremlinTraversal, call: CallExpr | MethodCallExpr
    ) -> None:
        _reject_unknown_kwargs(call, set())
        labels = _string_args(call)
        # `otherV()` means "the vertex on the other side of the current edge".
        # This matches Opium's edge-first traversal model better than compiling
        # traversal directly as `out()`/`in()`, because callers can project edge
        # documents before deciding to move into vertices.
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
            # `match` and `match_all` are currently equivalent: every condition
            # is appended as another Gremlin filter step, so they combine with
            # logical AND.
            traversal.extend(conditions)
            return

        # Gremlin `or(...)` expects anonymous traversals. Each compiled condition
        # starts with a dot, for example `.has(...)`, so prefixing `__` yields
        # valid children such as `__.has(...)`.
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
        # This is a first-pass implementation. It stores a folded child result
        # under a Gremlin label using `sideEffect`. The exact Opium semantics for
        # per-row assignment and later computed projection still need review, so
        # e2e tests keep complex assign/select cases skipped for now.
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
        # `select(...)` returns a map/document shape. Gremlin `project(...).by(...)`
        # matches that shape directly and makes missing property behavior
        # explicit through `_compile_by_projection`.
        traversal.add(f".project({render_label_args(names)})")

        for column in columns:
            traversal.add(f".by({_compile_by_projection(column)})")
        for _name, expr in computed:
            traversal.add(f".by({self._compile_projection_expr(expr)})")

    def _compile_projection_expr(self, expr: Expr) -> str:
        """Compile expressions allowed in computed `select` columns."""

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
            return self._compile_binary_condition(expr)

        msg = f"Unsupported match condition: {type(expr).__name__}"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_condition_call(self, call: CallExpr) -> str:
        """Compile function-style match conditions.

        Supported operands are field names and literal values. Parsed conditions
        involving subqueries or variables are intentionally rejected elsewhere
        until their Opium semantics are settled.
        """

        if call.function in {"match", "match_all", "match_any"}:
            conditions = [
                *_keyword_conditions(call.kwargs),
                *(self._compile_condition(arg) for arg in call.args),
            ]
            if call.function == "match_any":
                return f".or({', '.join(f'__{condition}' for condition in conditions)})"
            return "".join(conditions)

        if call.function == "eq":
            left, value = _operand_value_args(call)
            return self._compile_operand_condition(left, "eq", value)
        if call.function in {"lt", "gt", "lte", "gte"}:
            left, value = _operand_value_args(call)
            return self._compile_operand_condition(left, call.function, value)
        if call.function == "ne":
            left, value = _operand_value_args(call)
            return self._compile_operand_condition(left, "ne", value)
        if call.function == "value_in":
            left, value = _operand_value_args(call)
            return self._compile_operand_condition(left, "value_in", value)
        if call.function == "nin":
            left, value = _operand_value_args(call)
            return self._compile_operand_condition(left, "nin", value)
        if call.function == "is_null":
            field = _single_field_arg(call, "is_null")
            return _compile_null_condition(field)
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
            # Gremlin TextP.regex accepts Java regex syntax. Prefixing `(?i)` is
            # the least invasive way to implement Opium's `caseInsensitive`
            # option while leaving already-prefixed patterns unchanged.
            regex = f"(?i){regex}"
        return f".has({quote_groovy(field)}, TextP.regex({quote_groovy(regex)}))"

    def _compile_binary_condition(self, expr: BinaryOpExpr) -> str:
        op_by_symbol = {
            "==": "eq",
            "!=": "ne",
            "<": "lt",
            ">": "gt",
            "<=": "lte",
            ">=": "gte",
        }
        return self._compile_operand_condition(
            expr.left,
            op_by_symbol[expr.op],
            expr.right,
        )

    def _compile_operand_condition(self, left: Expr, op: str, value: Expr) -> str:
        """Compile a condition whose left operand may be a field or expression.

        Field operands compile to direct `has(...)` filters on the current row.
        Subscript operands such as `traverse().into()['_key']` compile to a
        `filter(...)` with an anonymous traversal from the current row. That
        implements the documented "subquery starts from the current row"
        semantics.
        """

        if _is_field_expr(left):
            return _compile_field_condition(_field_name(left), op, value)
        if isinstance(left, SubscriptExpr):
            child = self._compile_condition_operand_traversal(left.receiver)
            return f".filter({child}{_compile_field_condition(left.field, op, value)})"

        msg = f"Unsupported condition operand: {type(left).__name__}"
        raise UnsupportedOpiumCompilationError(msg)

    def _compile_condition_operand_traversal(self, expr: Expr) -> str:
        traversal = self._compile_traversal(expr, child=True).render()
        if traversal.startswith("__"):
            return traversal
        if traversal.startswith("select("):
            return f"__.{traversal}"

        msg = f"Unsupported condition traversal operand: {type(expr).__name__}"
        raise UnsupportedOpiumCompilationError(msg)


def _string_args(call: CallExpr | MethodCallExpr) -> list[str]:
    name = call.function if isinstance(call, CallExpr) else call.method
    return [_expect_string(arg, f"{name} arg") for arg in call.args]


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


def _operand_value_args(call: CallExpr) -> tuple[Expr, Expr]:
    if len(call.args) != 2 or call.kwargs:
        msg = f"{call.function}(...) expects exactly two positional arguments"
        raise InvalidOpiumSemanticError(msg)
    return call.args[0], call.args[1]


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


def _is_field_expr(expr: Expr) -> bool:
    return isinstance(expr, StringExpr | NameExpr)


def _ensure_list(expr: Expr) -> ListExpr:
    if not isinstance(expr, ListExpr):
        msg = "Expected a list literal"
        raise InvalidOpiumSemanticError(msg)
    return expr


def _compile_projection_step(field: str) -> str:
    # Subscript projection returns a one-field map, not a raw scalar. This keeps
    # `get('roles')['_key']` consistent with `select('_key')` and with the
    # project/document semantics recorded in the Opium semantics notes.
    return f".project({quote_groovy(field)}).by({_compile_by_projection(field)})"


def _compile_field_condition(field: str, op: str, value: Expr) -> str:
    if op == "eq":
        if field == "_key":
            return _compile_key_filter(value)
        return f".has({quote_groovy(field)}, {render_literal(value)})"
    if op == "ne":
        if field == "_key":
            return f".not(__{_compile_key_filter(value)})"
        return f".has({quote_groovy(field)}, {render_predicate('neq', value)})"
    if op in {"lt", "gt", "lte", "gte"}:
        if field == "_key":
            msg = "_key only supports equality-style comparisons"
            raise InvalidOpiumSemanticError(msg)
        return f".has({quote_groovy(field)}, {render_predicate(op, value)})"
    if op == "value_in":
        if field == "_key":
            return _compile_key_membership(value, negate=False)
        return f".has({quote_groovy(field)}, {render_within('within', value)})"
    if op == "nin":
        if field == "_key":
            return _compile_key_membership(value, negate=True)
        return f".has({quote_groovy(field)}, {render_within('without', value)})"

    msg = f"Unsupported condition operator: {op}"
    raise UnsupportedOpiumCompilationError(msg)


def _compile_null_condition(field: str) -> str:
    quoted = quote_groovy(field)
    return f".or(__.not(__.has({quoted})), __.has({quoted}, null))"


def _compile_by_projection(field: str) -> str:
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


def _compile_key_filter(value: Expr) -> str:
    if not isinstance(value, StringExpr):
        msg = "_key filters require a string literal"
        raise InvalidOpiumSemanticError(msg)
    # Because provider ids are `collection/key`, filtering by Opium `_key` uses
    # a suffix match. This assumes keys cannot contain collection separators in a
    # way that would make `/key` ambiguous.
    key_suffix = quote_groovy(f"/{value.value}")
    return f".hasId(TextP.endingWith({key_suffix}))"


def _compile_key_membership(value: Expr, *, negate: bool) -> str:
    items = _ensure_list(value).items
    filters = [f"__{_compile_key_filter(item)}" for item in items]
    if not filters:
        # Empty positive membership can match nothing. Empty negative membership
        # should match everything, represented as "not impossible".
        return ".not(__.identity())" if negate else ".filter(__.none())"

    joined = ", ".join(filters)
    if negate:
        return f".not(__.or({joined}))"
    return f".or({joined})"


def _is_deep_traverse_expr(expr: Expr) -> bool:
    if isinstance(expr, CallExpr) and expr.function in _TRAVERSE_NAMES:
        return _has_non_default_depth(expr)
    if isinstance(expr, MethodCallExpr) and expr.method in _TRAVERSE_NAMES:
        return _has_non_default_depth(expr)
    return False


def _traverse_receiver(expr: Expr) -> Expr:
    if isinstance(expr, MethodCallExpr):
        return expr.receiver
    if isinstance(expr, CallExpr):
        # Child subqueries such as `traverse(max_depth=2).into()` start from
        # `__`. We create an internal sentinel call rather than exposing a public
        # AST node just for this compiler implementation detail.
        return CallExpr(function="traverse_start", args=[], kwargs={})
    msg = "Expected traverse expression"
    raise InvalidOpiumSemanticError(msg)


def _has_non_default_depth(call: CallExpr | MethodCallExpr) -> bool:
    return (
        _optional_int_kwarg(call, "min_depth", default=1) != 1
        or _optional_int_kwarg(call, "max_depth", default=1) != 1
    )


def _compile_deep_traverse_step(
    call: CallExpr | MethodCallExpr, *, into: bool
) -> str:
    _reject_unknown_kwargs(call, {"min_depth", "max_depth", "direction"})
    min_depth = _optional_int_kwarg(call, "min_depth", default=1)
    max_depth = _optional_int_kwarg(call, "max_depth", default=1)
    if min_depth < 1 or max_depth < min_depth:
        msg = "traverse depth requires 1 <= min_depth <= max_depth"
        raise InvalidOpiumSemanticError(msg)

    repeat_body = _compile_deep_repeat_body(call)
    # `emit()` includes intermediate depths. For min_depth > 1, Gremlin's
    # `loops()` counter lets us suppress shallower hops while still repeating
    # through them to reach deeper results.
    emit = ".emit()" if min_depth == 1 else f".emit(loops().is(P.gte({min_depth})))"
    step = f".repeat({repeat_body}){emit}.times({max_depth})"
    if into:
        # When `into()` is present, the repeat body has already moved from each
        # edge to the next vertex, so emitted traversers are vertices.
        return step
    # Without `into()`, Opium traversal returns edge documents. The repeat body
    # labels the edge before moving to the next vertex, then we select that edge
    # back out for the result stream.
    return f"{step}.select('opium_edge')"


def _compile_deep_repeat_body(call: CallExpr | MethodCallExpr) -> str:
    labels = render_label_args(_string_args(call))
    direction = _direction(call)
    if direction == "outbound":
        return f"outE({labels}).as('opium_edge').inV()"
    if direction == "inbound":
        return f"inE({labels}).as('opium_edge').outV()"
    return f"bothE({labels}).as('opium_edge').otherV()"


_TRAVERSE_NAMES = frozenset(
    {"traverse", "traverse_any", "traverse_out", "traverse_in"}
)
