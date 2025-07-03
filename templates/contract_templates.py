# templates.py
def get_template_content(template_type: str) -> str:
    """
    Get the content for a template contract file.
    
    Args:
        template_type: Type of template to get ("basic", "full", or "openapi")
        
    Returns:
        YAML content for the template
    """
    if template_type == "basic":
        return """# Basic Mock API Contract
routes:
  - path: /hello
    method: GET
    response_stub:
      status_code: 200
      body:
        message: "Hello, World!"

  - path: /users
    method: GET
    response_stub:
      status_code: 200
      body:
        users:
          - id: "1"
            name: "John Doe"
          - id: "2"
            name: "Jane Smith"

  - path: /users/{userId}
    method: GET
    path_parameters:
      - name: userId
        type: string
        required: true
    response_stub:
      status_code: 200
      body:
        id: "{userId}"
        name: "User {userId}"
        email: "user{userId}@example.com"
"""
    elif template_type == "full":
        return """# Full-featured Mock API Contract
routes:
  - id: get_users
    path: /api/users
    method: GET
    description: "Get a list of all users"
    query_parameters:
      page:
        name: page
        type: integer
        required: false
        description: "Page number for pagination"
      limit:
        name: limit
        type: integer
        required: false
        description: "Number of items per page"
    request_headers:
      Authorization: null
    response_stub:
      status_code: 200
      headers:
        Content-Type: "application/json"
      body:
        users:
          - id: "1"
            name: "John Doe"
            email: "john@example.com"
          - id: "2" 
            name: "Jane Smith"
            email: "jane@example.com"
        pagination:
          total: 50
          page: 1
          limit: 10

  - id: create_user
    path: /api/users
    method: POST
    description: "Create a new user"
    request_headers:
      Content-Type: "application/json"
      Authorization: null
    request_body_schema:
      type: object
      required: ["name", "email"]
      properties:
        name:
          type: string
          minLength: 2
        email:
          type: string
          format: email
        age:
          type: integer
          minimum: 18
    response_stub:
      status_code: 201
      headers:
        Content-Type: "application/json"
        Location: "/api/users/3"
      body:
        id: "3"
        name: "{request.body.name}"
        email: "{request.body.email}"
        created_at: "{now}"

  - id: get_user_by_id
    path: /api/users/{userId}
    method: GET
    description: "Get a user by ID"
    path_parameters:
      - name: userId
        type: string
        required: true
        description: "The user's unique identifier"
    request_headers:
      Authorization: null
    response_stub:
      status_code: 200
      body:
        id: "{userId}"
        name: "User {userId}"
        email: "user{userId}@example.com"

  - id: user_not_found
    path: /api/users/{userId}
    method: GET
    description: "User not found response"
    path_parameters:
      - name: userId
        type: string
        required: true
    request_headers:
      Authorization: null
    response_stub:
      status_code: 404
      body:
        error: "User not found"
        message: "No user found with ID {userId}"
"""
    elif template_type == "openapi":
        return """# OpenAPI-style Mock API Contract
openapi: "3.0.0"
info:
  title: "Sample API"
  version: "1.0.0"
servers:
  - url: "http://localhost:8000"
    description: "Local development server"

routes:
  - path: /pets
    method: GET
    description: "Returns all pets from the system"
    query_parameters:
      tags:
        name: tags
        type: array
        required: false
        description: "Tags to filter by"
      limit:
        name: limit
        type: integer
        required: false
        description: "Maximum number of results to return"
    response_stub:
      status_code: 200
      headers:
        Content-Type: "application/json"
      body:
        - id: 1
          name: "Dog"
          tag: "canine"
        - id: 2
          name: "Cat"
          tag: "feline"

  - path: /pets
    method: POST
    description: "Creates a new pet in the store"
    request_headers:
      Content-Type: "application/json"
    request_body_schema:
      type: object
      required: ["name"]
      properties:
        name:
          type: string
          minLength: 1
        tag:
          type: string
    response_stub:
      status_code: 201
      body:
        id: 3
        name: "{request.body.name}"
        tag: "{request.body.tag}"

  - path: /pets/{petId}
    method: GET
    description: "Returns a pet by ID"
    path_parameters:
      - name: petId
        type: integer
        required: true
        description: "ID of the pet to return"
    response_stub:
      status_code: 200
      body:
        id: "{petId}"
        name: "Pet {petId}"
        tag: "tag{petId}"
"""
    else:
        raise ValueError(f"Unknown template type: {template_type}")