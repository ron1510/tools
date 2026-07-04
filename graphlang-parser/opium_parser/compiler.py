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

import logging
from typing import cast

from opium_parser.ast_nodes import (
    CallExpr,
    Expr,
    MethodCallExpr,
    Query,
    StringExpr,
    SubscriptExpr,
)
from opium_parser.compiler_common import (
    TRAVERSE_NAMES,
    compile_key_filter,
    deep_repeat_body,
    direction,
    endpoint_vertex_step,
    parse_depth_range,
    parse_empty_method_call,
    parse_flatten_depth,
    parse_limit_count,
    parse_no_positional_args,
    parse_single_expr_arg,
    parse_skip_count,
    parse_string_literal,
    parse_supported_kwargs,
    parse_variable_name_arg,
    render_resource_args,
    string_args,
)
from opium_parser.compiler_match import apply_match
from opium_parser.compiler_projection import (
    compile_by_projection,
    compile_edge_document_step,
    compile_projection_expr,
    compile_projection_step,
)
from opium_parser.errors import (
    InvalidOpiumSemanticError,
    OpiumCompilerError,
    OpiumParserError,
    UnsupportedOpiumCompilationError,
    error_context,
)
from opium_parser.gremlin_ir import EdgeDirection, GremlinTraversal
from opium_parser.gremlin_renderer import (
    quote_groovy,
    render_label_args,
)
from opium_parser.observability import (
    COMPILE_FAILED,
    COMPILE_INTERNAL_ERROR,
    COMPILE_STARTED,
    COMPILE_SUCCEEDED,
    elapsed_ms,
    error_fields,
    event_fields,
    source_fields,
    start_timer,
)
from opium_parser.parser import _parse_opium
from opium_parser.types import GremlinGroovyString

logger = logging.getLogger(__name__)


def compile_opium_to_gremlin(source: str) -> GremlinGroovyString:
    """Parse an Opium expression and compile it into a Gremlin Groovy string."""

    total_started_ns = start_timer()
    fields = source_fields(source)
    logger.debug(
        "Compiling Opium query",
        extra=event_fields(COMPILE_STARTED, **fields),
    )

    parse_started_ns = start_timer()
    parse_duration_ms: float | None = None
    compile_started_ns: int | None = None
    try:
        query = _parse_opium(source)
        parse_duration_ms = elapsed_ms(parse_started_ns)
        compile_started_ns = start_timer()
        gremlin = _compile_query(query)
        compile_duration_ms = elapsed_ms(compile_started_ns)
    except (OpiumParserError, OpiumCompilerError) as exc:
        failed_parse_duration_ms = (
            elapsed_ms(parse_started_ns)
            if parse_duration_ms is None
            else parse_duration_ms
        )
        failed_compile_duration_ms = (
            None if compile_started_ns is None else elapsed_ms(compile_started_ns)
        )
        logger.warning(
            "Opium query compilation failed",
            extra=event_fields(
                COMPILE_FAILED,
                **fields,
                parse_duration_ms=failed_parse_duration_ms,
                compile_duration_ms=failed_compile_duration_ms,
                total_duration_ms=elapsed_ms(total_started_ns),
                **error_fields(exc.detail),
            ),
        )
        raise
    except Exception:
        failed_parse_duration_ms = (
            elapsed_ms(parse_started_ns)
            if parse_duration_ms is None
            else parse_duration_ms
        )
        failed_compile_duration_ms = (
            None if compile_started_ns is None else elapsed_ms(compile_started_ns)
        )
        logger.exception(
            "Unexpected Opium compiler failure",
            extra=event_fields(
                COMPILE_INTERNAL_ERROR,
                **fields,
                parse_duration_ms=failed_parse_duration_ms,
                compile_duration_ms=failed_compile_duration_ms,
                total_duration_ms=elapsed_ms(total_started_ns),
            ),
        )
        raise

    logger.info(
        "Compiled Opium query",
        extra=event_fields(
            COMPILE_SUCCEEDED,
            **fields,
            ast_root_kind=query.root.kind,
            gremlin_query=str(gremlin),
            gremlin_query_length=len(gremlin),
            parse_duration_ms=parse_duration_ms,
            compile_duration_ms=compile_duration_ms,
            total_duration_ms=elapsed_ms(total_started_ns),
        ),
    )
    return gremlin


def compile_ast_to_gremlin(query: Query) -> GremlinGroovyString:
    """Compile a typed Opium AST into a Gremlin Groovy string."""

    started_ns = start_timer()
    logger.debug(
        "Compiling Opium AST",
        extra=event_fields(
            COMPILE_STARTED,
            ast_root_kind=query.root.kind,
        ),
    )
    try:
        gremlin = _compile_query(query)
    except OpiumCompilerError as exc:
        logger.warning(
            "Opium AST compilation failed",
            extra=event_fields(
                COMPILE_FAILED,
                ast_root_kind=query.root.kind,
                compile_duration_ms=elapsed_ms(started_ns),
                total_duration_ms=elapsed_ms(started_ns),
                **error_fields(exc.detail),
            ),
        )
        raise
    except Exception:
        logger.exception(
            "Unexpected Opium AST compiler failure",
            extra=event_fields(
                COMPILE_INTERNAL_ERROR,
                ast_root_kind=query.root.kind,
                compile_duration_ms=elapsed_ms(started_ns),
                total_duration_ms=elapsed_ms(started_ns),
            ),
        )
        raise

    duration_ms = elapsed_ms(started_ns)
    logger.info(
        "Compiled Opium AST",
        extra=event_fields(
            COMPILE_SUCCEEDED,
            ast_root_kind=query.root.kind,
            gremlin_query=str(gremlin),
            gremlin_query_length=len(gremlin),
            compile_duration_ms=duration_ms,
            total_duration_ms=duration_ms,
        ),
    )
    return gremlin


def _compile_query(query: Query) -> GremlinGroovyString:
    """Compile the root traversal for a parsed Opium query.

    The compiler walks from the root expression down through receivers, then
    appends Gremlin steps as it unwinds. That mirrors how a chained Opium query
    is read:

    `get('roles').traverse_out('edges').into('roles')`

    becomes:

    `g.V().hasLabel('roles').outE('edges').otherV().hasLabel('roles')`
    """

    traversal = _compile_traversal(query.root, child=False)
    if traversal.cursor_kind == "edge":
        traversal.add(compile_edge_document_step())
        traversal.set_cursor("map")
    return traversal.render()


def _compile_traversal(expr: Expr, *, child: bool) -> GremlinTraversal:
    """Compile an expression that should behave as a traversal.

    `child=True` means the expression is nested inside another traversal, for
    example `array(traverse().into())`. In that mode we start from `__` where
    possible so Gremlin treats the generated traversal as local to the current
    traverser.
    """

    if isinstance(expr, CallExpr):
        return _compile_call(expr, child=child)
    if isinstance(expr, MethodCallExpr):
        # Deep traversal followed by `into()` needs special handling because the
        # repeat body must move edge -> vertex on every hop. Compiling
        # `.traverse(max_depth=3)` first would leave the traversal on edges,
        # which is correct only when `into()` is not present.
        if expr.method == "into" and _is_deep_traverse_expr(expr.receiver):
            assert isinstance(expr.receiver, CallExpr | MethodCallExpr)
            traversal = _deep_traverse_start(expr.receiver, child=child)
            _apply_deep_traverse_into(traversal, expr.receiver, expr)
            return traversal
        traversal = _compile_traversal(expr.receiver, child=child)
        _apply_method(traversal, expr)
        return traversal
    if isinstance(expr, SubscriptExpr):
        traversal = _compile_traversal(expr.receiver, child=child)
        traversal.add(compile_projection_step(expr.field))
        traversal.set_cursor("scalar")
        return traversal

    msg = f"Cannot compile {type(expr).__name__} as a Gremlin traversal"
    raise UnsupportedOpiumCompilationError(msg)


def _compile_call(call: CallExpr, *, child: bool) -> GremlinTraversal:
    match str(call.function):
        case "get":
            if child:
                # `get(...)` inside a local child traversal would restart from
                # the whole graph rather than the current traverser. Opium may
                # eventually define that behavior, but it is not part of the
                # validated subset.
                msg = "get(...) is only supported as a root traversal for now"
                raise UnsupportedOpiumCompilationError(
                    msg,
                    code="compile.unsupported_root",
                    context={"function": "get", "position": "child"},
                )
            if not call.args:
                msg = "get(...) requires at least one resource"
                raise InvalidOpiumSemanticError(
                    msg,
                    code="semantic.invalid_argument_count",
                    expected=("at least one resource",),
                    actual="0",
                    context={"function": "get"},
                )
            traversal = GremlinTraversal("g.V()", cursor_kind="vertex")
            traversal.add(f".hasLabel({render_resource_args(call)})")
            if "_key" in call.kwargs:
                traversal.add(compile_key_filter(call.kwargs["_key"]))
            parse_supported_kwargs(call, {"_key"})
            return traversal
        case "traverse" | "traverse_any" | "traverse_out" | "traverse_in":
            # Top-level `traverse(...)` is syntactically valid Opium, but as a
            # Gremlin traversal it needs a starting point. We use `g.V()` at the
            # top level and `__` for child traversals, matching the parser's
            # policy of allowing syntax before all semantic combinations are
            # necessarily recommended.
            traversal = _traversal_start(child=child)
            _apply_traverse(traversal, call)
            return traversal
        case "into":
            # Standalone `into()` starts from edges. In normal use it is chained
            # after `traverse`, but accepting it here keeps the compiler behavior
            # consistent with the parser's allowed top-level call names.
            traversal = GremlinTraversal(
                "__" if child else "g.E()",
                cursor_kind="edge",
                edge_direction="any",
            )
            _apply_into(traversal, call)
            return traversal
        case "var":
            # `var('x')` compiles to Gremlin `select('x')`. Whether a label `x`
            # is actually in scope depends on the surrounding query and is not
            # fully validated by this compiler yet.
            name = parse_variable_name_arg(call, "var")
            return GremlinTraversal(f"select({quote_groovy(name)})")
        case function:
            msg = f"{function}(...) cannot start a Gremlin traversal"
            raise UnsupportedOpiumCompilationError(
                msg,
                code="compile.unsupported_root",
                actual=function,
            )


def _apply_method(traversal: GremlinTraversal, call: MethodCallExpr) -> None:
    match str(call.method):
        case "traverse" | "traverse_any" | "traverse_out" | "traverse_in":
            _apply_traverse(traversal, call)
        case "into":
            _apply_into(traversal, call)
        case "skip":
            traversal.add(f".skip({parse_skip_count(call)})")
        case "limit":
            traversal.add(f".limit({parse_limit_count(call)})")
        case "count":
            parse_empty_method_call(call)
            traversal.add(".count()")
            traversal.set_cursor("scalar")
        case "unique":
            parse_empty_method_call(call)
            traversal.add(".dedup()")
        case "as_var":
            name = parse_variable_name_arg(call, "as_var")
            traversal.add(f".as({quote_groovy(name)})")
        case "match" | "match_all" | "match_any":
            apply_match(
                traversal,
                call.method,
                call.args,
                call.kwargs,
                _compile_condition_operand_traversal,
            )
        case "array":
            # Current interpretation: `array(subquery)` runs a local child
            # traversal for each incoming traverser and folds its results into a
            # list. This covers the simple documented shapes, but nested/scoped
            # array behavior is still marked as incomplete in docs and tests.
            subquery = parse_single_expr_arg(call, "array")
            child = _compile_traversal(subquery, child=True).render()
            traversal.add(f".local({child}).fold()")
            traversal.set_cursor("list")
        case "flatten":
            # `flatten()` is represented as one `unfold()`. `flatten(depth=N)`
            # repeats `unfold()` N times. This is a simple Gremlin mapping, not
            # a complete commitment about every nested Opium array shape.
            depth = parse_flatten_depth(call)
            parse_no_positional_args(call, "flatten")
            traversal.extend([".unfold()" for _ in range(depth)])
            if depth > 0:
                traversal.set_cursor("unknown")
        case "assign":
            _apply_assign(traversal, call)
        case "select":
            _apply_select(traversal, call)
        case method:
            msg = f"Unsupported method for Gremlin compilation: {method}"
            raise UnsupportedOpiumCompilationError(
                msg,
                code="compile.unsupported_method",
                actual=method,
            )


def _apply_traverse(
    traversal: GremlinTraversal, call: CallExpr | MethodCallExpr
) -> None:
    traversal_direction = direction(call)
    depth_range = parse_depth_range(call)
    parse_supported_kwargs(call, {"min_depth", "max_depth", "direction"})

    if depth_range.min_depth != 1 or depth_range.max_depth != 1:
        # Deep traversal has to remember the edge taken at each hop because
        # Opium `traverse(...)` returns edges, while `traverse(...).into()`
        # returns vertices. The repeat body therefore labels each edge as
        # `opium_edge` before moving to the adjacent vertex.
        traversal.add(_compile_deep_traverse_step(call, into=False))
        traversal.set_cursor(
            "edge",
            edge_direction=cast(EdgeDirection, str(traversal_direction)),
        )
        return

    # Default traversal returns edges. `into()` is a separate Opium step that
    # converts those edges to the opposite endpoint vertex.
    if str(traversal_direction) == "any":
        traversal.add(".as('opium_current_vertex')")
    step = {"any": "bothE", "outbound": "outE", "inbound": "inE"}[
        str(traversal_direction)
    ]
    traversal.add(f".{step}({render_resource_args(call)})")
    traversal.set_cursor(
        "edge",
        edge_direction=cast(EdgeDirection, str(traversal_direction)),
    )


def _apply_deep_traverse_into(
    traversal: GremlinTraversal,
    traverse_call: CallExpr | MethodCallExpr,
    into_call: MethodCallExpr,
) -> None:
    traversal.add(_compile_deep_traverse_step(traverse_call, into=True))
    parse_supported_kwargs(into_call, set())
    labels = string_args(into_call)
    if labels:
        traversal.add(f".hasLabel({render_resource_args(into_call)})")
    traversal.set_cursor("vertex")


def _apply_into(traversal: GremlinTraversal, call: CallExpr | MethodCallExpr) -> None:
    parse_supported_kwargs(call, set())
    labels = string_args(call)
    if traversal.cursor_kind != "edge":
        msg = "into(...) requires the current traversal to contain edge documents"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_into_cursor",
            expected=("edge cursor",),
            actual=traversal.cursor_kind,
            context=error_context(method="into"),
        )
    traversal.add(_vertex_step_for_edge_cursor(traversal))
    if labels:
        traversal.add(f".hasLabel({render_resource_args(call)})")
    traversal.set_cursor("vertex")


def _vertex_step_for_edge_cursor(traversal: GremlinTraversal) -> str:
    return endpoint_vertex_step(traversal.edge_direction or "any")


def _apply_assign(traversal: GremlinTraversal, call: MethodCallExpr) -> None:
    if len(call.args) != 2 or call.kwargs:
        msg = "assign(...) expects (sub_query, var_name)"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("sub_query", "var_name"),
            actual=f"{len(call.args)} positional, {len(call.kwargs)} keyword",
            context={"method": "assign"},
        )
    subquery, var_name_expr = call.args
    if not isinstance(var_name_expr, StringExpr):
        msg = "assign(...) var_name must be a string literal"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_type",
            expected=("string",),
            actual=type(var_name_expr).__name__,
            context={"method": "assign", "argument": "var_name"},
        )
    child = _compile_traversal(subquery, child=True).render()
    # This is a first-pass implementation. It stores a folded child result
    # under a Gremlin label using `sideEffect`. The exact Opium semantics for
    # per-row assignment and later computed projection still need review, so
    # e2e tests keep complex assign/select cases skipped for now.
    traversal.add(
        f".sideEffect({child}.fold().as({quote_groovy(var_name_expr.value)}))"
    )


def _apply_select(traversal: GremlinTraversal, call: MethodCallExpr) -> None:
    columns = [parse_string_literal(arg, "select column") for arg in call.args]
    computed = list(call.kwargs.items())
    if not columns and not computed:
        msg = "select(...) requires at least one column"
        raise InvalidOpiumSemanticError(
            msg,
            code="semantic.invalid_argument_count",
            expected=("at least one selected column",),
            actual="0",
            context={"method": "select"},
        )

    names = [*columns, *(name for name, _expr in computed)]
    # `select(...)` returns a map/document shape. Gremlin `project(...).by(...)`
    # matches that shape directly and makes missing property behavior
    # explicit through `compile_by_projection`.
    traversal.add(f".project({render_label_args(names)})")

    for column in columns:
        traversal.add(f".by({compile_by_projection(column)})")
    for _name, expr in computed:
        traversal.add(f".by({compile_projection_expr(expr)})")
    traversal.set_cursor("map")


def _compile_condition_operand_traversal(expr: Expr) -> str:
    traversal = _compile_traversal(expr, child=True).render()
    if traversal.startswith("__"):
        return traversal
    if traversal.startswith("select("):
        return f"__.{traversal}"

    msg = f"Unsupported condition traversal operand: {type(expr).__name__}"
    raise UnsupportedOpiumCompilationError(
        msg,
        code="compile.unsupported_expression",
        actual=type(expr).__name__,
        context={"position": "match operand"},
    )


def _is_deep_traverse_expr(expr: Expr) -> bool:
    if isinstance(expr, CallExpr) and expr.function in TRAVERSE_NAMES:
        return _has_non_default_depth(expr)
    if isinstance(expr, MethodCallExpr) and expr.method in TRAVERSE_NAMES:
        return _has_non_default_depth(expr)
    return False


def _deep_traverse_start(
    expr: CallExpr | MethodCallExpr, *, child: bool
) -> GremlinTraversal:
    if isinstance(expr, MethodCallExpr):
        return _compile_traversal(expr.receiver, child=child)
    return _traversal_start(child=child)


def _traversal_start(*, child: bool) -> GremlinTraversal:
    return GremlinTraversal("__" if child else "g.V()", cursor_kind="vertex")


def _has_non_default_depth(call: CallExpr | MethodCallExpr) -> bool:
    depth_range = parse_depth_range(call)
    return depth_range.min_depth != 1 or depth_range.max_depth != 1


def _compile_deep_traverse_step(call: CallExpr | MethodCallExpr, *, into: bool) -> str:
    parse_supported_kwargs(call, {"min_depth", "max_depth", "direction"})
    depth_range = parse_depth_range(call)
    min_depth = depth_range.min_depth
    max_depth = depth_range.max_depth

    repeat_body = deep_repeat_body(call)
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
