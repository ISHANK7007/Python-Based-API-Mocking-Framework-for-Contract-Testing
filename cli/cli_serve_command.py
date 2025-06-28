# Output_code/cli/cli_serve_command.py

import os
from contract.contract_loader import ContractLoader
from core.server_factory import create_server

def handle_serve_command(args) -> int:
    """
    Handles the 'serve' CLI command by starting the mock API server.
    """
    contract_path = args.contract_path

    # Load contracts
    contracts = ContractLoader.load_from_path(contract_path)

    # Create and run the server
    app, shutdown_event = create_server(
        contracts=contracts,
        use_trie=True,
        strict_validation=args.strict_validation
    )

    print(f"🚀 Mock API server running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, use_reloader=args.reload)

    return 0
