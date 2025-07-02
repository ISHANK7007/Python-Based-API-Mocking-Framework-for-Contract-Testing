from dataclasses import dataclass, field, asdict
from typing import Optional, Tuple, FrozenSet


@dataclass(frozen=True)
class RouteSignature:
    """
    Represents the essential characteristics of an API route,
    used for efficient route comparison during contract diffing.
    """
    path: str
    method: str
    description: Optional[str] = None
    request_schema_hash: Optional[str] = None
    response_schema_hashes: FrozenSet[Tuple[str, str]] = field(default_factory=frozenset)
