class MockResponseGenerator:
    def __init__(self, contract, chaos_middleware):
        self.contract = contract
        self.chaos_middleware = chaos_middleware

    def get_response(self, route, method, request_context):
        """
        Simulates a route+method handler passed through the chaos middleware.
        Returns a dict representing the response.
        """
        def base_response():
            return {
                "status_code": 200,
                "body": {"message": "OK"}
            }

        wrapped = self.chaos_middleware.apply(route, method, base_response)
        return wrapped(request_context=request_context)
