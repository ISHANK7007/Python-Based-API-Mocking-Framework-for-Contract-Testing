import time
import logging
from typing import List, Optional, Union
from pathlib import Path

from contract.contract_entry import ContractEntry, HttpMethod
from router.route_registry import RouteRegistry
from schema.validator import SchemaValidator

logger = logging.getLogger(__name__)


def start_server(
    contracts: List[ContractEntry],
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    contract_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Start the mock API server (stub version).

    Args:
        contracts: List of contract entries to serve
        host: Host address to bind to
        port: Port to listen on
        reload: Whether to automatically reload when contracts change
        contract_path: Path to the contract file (for reload functionality)
    """
    logger.info(f"🚀 Starting mock API server on {host}:{port}")
    logger.info(f"🔧 Loaded {len(contracts)} contract routes")

    # Route registry
    registry = RouteRegistry()
    registry.register_many(contracts)

    # Validation logic placeholder
    validator = SchemaValidator()

    # Log registered routes by method
    for method in [HttpMethod.GET, HttpMethod.POST, HttpMethod.PUT, HttpMethod.DELETE]:
        routes = registry.get_routes(method)
        if routes:
            logger.info(f"{method.value}: {len(routes)} routes")
            for route in routes:
                logger.info(f"  ↪ {route.path}")

    if reload and contract_path:
        logger.info(f"🔄 Auto-reload enabled, watching {contract_path}")

    logger.info("✅ Server initialized (stub only) — replace with real server framework (e.g., FastAPI)")
    logger.info("🕓 Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
