import argparse
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Union

from contract.contract_loader import ContractLoader, ContractLoadError
from contract.contract_entry import ContractEntry
from templates.contract_templates import get_template_content
from contract.compatibility_checker import compatibility_check  # ✅ required for check-compatibility

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=log_level, format=log_format)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("jsonschema").setLevel(logging.WARNING)


def validate_contract_file(contract_path: Union[str, Path]) -> List[ContractEntry]:
    contract_path = Path(contract_path)
    if not contract_path.exists():
        raise ValueError(f"Contract file not found: {contract_path}")
    if not os.access(contract_path, os.R_OK):
        raise ValueError(f"Contract file is not readable: {contract_path}")
    if contract_path.suffix.lower() not in ('.yaml', '.yml'):
        raise ValueError(f"Contract file must be a YAML file: {contract_path}")

    try:
        contracts = ContractLoader.load_from_file(contract_path)
        if not contracts:
            raise ValueError(f"Contract file contains no valid entries: {contract_path}")
        return contracts
    except ContractLoadError as e:
        raise ValueError(f"Error loading contract file: {e.message}\n{e.details or ''}")
    except Exception as e:
        raise ValueError(f"Unexpected error loading contract file: {str(e)}")


def handle_check_compatibility(args: argparse.Namespace) -> int:
    """✅ FIXED: Implements compatibility check command."""
    try:
        is_compatible, reasons, details = compatibility_check(
            from_file=args.from_file,
            to_file=args.to_file,
            include_non_breaking=args.include_non_breaking,
            severity=args.severity,
            output_json=args.json_output,
            quiet=args.quiet,
        )

        if is_compatible:
            if not args.quiet:
                print("✓ Compatible: No breaking changes found.")
            return 0
        else:
            if not args.quiet:
                print("✗ Compatibility issues detected:")
                for reason in reasons:
                    print(f"  - {reason}")
            return 1
    except Exception as e:
        print(f"✗ Error during compatibility check: {e}", file=sys.stderr)
        return 1


def handle_serve_command(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    logger.info(f"Starting mock API server on {args.host}:{args.port}")

    try:
        contracts = validate_contract_file(args.contract)
        logger.info(f"Loaded {len(contracts)} contract entries from {args.contract}")

        from core.server import start_server
        start_server(
            contracts=contracts,
            host=args.host,
            port=args.port,
            reload=args.reload,
            contract_path=args.contract
        )
        return 0
    except ValueError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def handle_validate_command(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    try:
        contracts = validate_contract_file(args.contract)
        print(f"✓ Contract file is valid: {args.contract}")
        print(f"✓ {len(contracts)} contract entries loaded successfully")
        for i, contract in enumerate(contracts, 1):
            print(f"  {i}. {contract.method.value} {contract.path}")
        return 0
    except ValueError as e:
        print(f"✗ Validation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        return 1


def handle_generate_command(args: argparse.Namespace) -> int:
    try:
        output_path = Path(args.output)
        if output_path.exists():
            confirm = input(f"File {output_path} already exists. Overwrite? (y/n): ")
            if confirm.lower() != 'y':
                print("Aborted.")
                return 0

        content = get_template_content(args.template)
        with output_path.open('w') as f:
            f.write(content)

        print(f"✓ Sample contract file generated: {output_path}")
        return 0
    except Exception as e:
        print(f"✗ Error generating template: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Contract validator CLI")
    args = parser.parse_args(argv)

    if args.command == "serve":
        return handle_serve_command(args)
    elif args.command == "validate":
        return handle_validate_command(args)
    elif args.command == "generate":
        return handle_generate_command(args)
    elif args.command == "check-compatibility":
        return handle_check_compatibility(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
