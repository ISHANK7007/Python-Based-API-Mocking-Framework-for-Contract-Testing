import logging
from pathlib import Path
from contract.contract_loader import ContractLoader, ContractLoadError  # fallback to basic loader
from cli.cli_validator import setup_logging


def handle_validate_command(args) -> int:
    """
    Handles the 'validate' command from the CLI.
    Validates one or more contract files.
    """
    setup_logging(args.verbose)
    contract_path = Path(args.path)

    try:
        if contract_path.is_dir():
            entries = ContractLoader.load_from_directory(contract_path)
        else:
            entries = ContractLoader.load_from_file(contract_path)

        logging.info(f"✅ Loaded {len(entries)} contract entries successfully.")
        print(f"\n✅ Contract validation succeeded for: {contract_path}")
        return 0

    except ContractLoadError as e:
        logging.error(f"❌ Validation failed: {e}")
        print(f"\n❌ Contract validation failed for: {contract_path}")
        print(f"Reason: {e}")
        return 1
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")
        print(f"\n❌ Unexpected error during validation: {e}")
        return 1
