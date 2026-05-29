from opium_parser import compile_opium_to_gremlin


def test_compile_as_var():
    assert (
        compile_opium_to_gremlin("get('users').as_var('user')")
        == "g.V().hasLabel('users').as('user')"
    )


def test_compile_assign():
    assert (
        compile_opium_to_gremlin(
            "get('users').assign(traverse().into(), 'neighborhood')"
        )
        == "g.V().hasLabel('users')"
        ".sideEffect(__.bothE().otherV().fold().as('neighborhood'))"
    )


def test_compile_select_columns_and_computed_var_projection():
    assert (
        compile_opium_to_gremlin(
            "get('users').assign(traverse().into(), 'neighborhood')"
            ".select('_key', neighbors=var('neighborhood')['_key'])"
        )
        == "g.V().hasLabel('users')"
        ".sideEffect(__.bothE().otherV().fold().as('neighborhood'))"
        ".project('_key', 'neighbors')"
        ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)})"
        ".by(select('neighborhood')"
        ".project('_key')"
        ".by(__.id().map{it.get().substring(it.get().lastIndexOf('/') + 1)}))"
    )
