from enum import Enum

class TokenType(Enum):
    FIELD = "FIELD"
    VALUE = "VALUE"
    OPERATOR = "OPERATOR"
    ARRAY_ACCESS = "ARRAY_ACCESS"
    DOT = "DOT"
    UNKNOWN = "UNKNOWN"
