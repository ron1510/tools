from opium_parser import MethodCallExpr, Query, parse_opium


def test_ast_models_serialize_with_discriminators():
    query = parse_opium("get('users-data-product.user_roles').limit(100)")

    assert isinstance(query, Query)
    assert isinstance(query.root, MethodCallExpr)

    dumped = query.model_dump()

    assert dumped == {
        "root": {
            "kind": "method_call",
            "receiver": {
                "kind": "call",
                "function": "get",
                "args": [
                    {
                        "kind": "string",
                        "value": "users-data-product.user_roles",
                    }
                ],
                "kwargs": {},
            },
            "method": "limit",
            "args": [
                {
                    "kind": "number",
                    "value": 100,
                }
            ],
            "kwargs": {},
        }
    }

    assert Query.model_validate(dumped) == query
