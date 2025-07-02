from contract.contract_entry import ContractEntry, HttpMethod, PathParameter, ResponseStub
from router.route_registry import RouteRegistry


def example_usage():
    # Create contract entries
    contract1 = ContractEntry(
        method=HttpMethod.GET,
        path="/users",
        response_stub=ResponseStub(status_code=200, body={"users": []})
    )

    contract2 = ContractEntry(
        method=HttpMethod.GET,
        path="/users/{userId}",
        path_parameters=[PathParameter(name="userId")],
        response_stub=ResponseStub(status_code=200, body={"id": "123", "name": "Test User"})
    )

    contract3 = ContractEntry(
        method=HttpMethod.GET,
        path="/users/{userId}/posts/{postId}",
        path_parameters=[
            PathParameter(name="userId"),
            PathParameter(name="postId")
        ],
        response_stub=ResponseStub(status_code=200, body={"title": "Test Post"})
    )

    contract4 = ContractEntry(
        method=HttpMethod.GET,
        path="/api/*",
        response_stub=ResponseStub(status_code=200)
    )

    # Register contracts in the RouteRegistry
    registry = RouteRegistry()
    registry.register_many([contract1, contract2, contract3, contract4])

    # Match examples
    match1 = registry.match(HttpMethod.GET, "/users")
    print("Match1 (Exact):", match1)

    match2 = registry.match(HttpMethod.GET, "/users/123")
    print("Match2 (Parameterized):", match2)

    match3 = registry.match(HttpMethod.GET, "/users/123/posts/456")
    print("Match3 (Nested Parameterized):", match3)

    match4 = registry.match(HttpMethod.GET, "/api/whatever")
    print("Match4 (Wildcard):", match4)

    # Find all matches for a given path (for debug purposes)
    all_matches = registry.find_all_matches(HttpMethod.GET, "/api/users")
    print("All Matches for '/api/users':")
    for m in all_matches:
        print("-", m)

    # Get all registered GET routes
    get_routes = registry.get_routes(HttpMethod.GET)
    print("All GET routes registered:", [r.path for r in get_routes])
