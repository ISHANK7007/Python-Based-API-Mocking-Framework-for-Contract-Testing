# Breaking Changes - Critical Severity
CRITICAL_BREAKING_CHANGES = {
    "REMOVED_ENDPOINT": {
        "code": "C001",
        "message": "Endpoint was removed",
        "description": "An API endpoint that existed in the previous version has been removed entirely"
    },
    "CHANGED_RESPONSE_STATUS": {
        "code": "C002",
        "message": "Success response status code changed",
        "description": "The HTTP status code for a successful response has changed (e.g., from 200 to 201)"
    },
    "REMOVED_SUCCESS_RESPONSE": {
        "code": "C003",
        "message": "Success response was removed",
        "description": "A successful response (2xx) that was previously supported is no longer available"
    }
}