from pathlib import Path
import os
from typing import List, Union

from contract.contract_entry import ContractEntry
from contract.contract_loader_unified import EnhancedContractLoader, ContractConflictError
from contract.contract_loader import ContractLoadError


def validate_contract_file(contract_path: Union[str, Path], allow_duplicates: bool = False) -> List[ContractEntry]:
    """
    Validate that a contract file exists and can be loaded properly.

    Args:
        contract_path: Path to the contract file
        allow_duplicates: If True, allow duplicate route definitions

    Returns:
        List of ContractEntry objects loaded from the file

    Raises:
        ValueError: If the file doesn't exist or can't be loaded
    """
    contract_path = Path(contract_path)

    if not contract_path.exists():
        raise ValueError(f"Contract file not found: {contract_path}")

    if not os.access(contract_path, os.R_OK):
        raise ValueError(f"Contract file is not readable: {contract_path}")

    if contract_path.suffix.lower() not in ('.yaml', '.yml'):
        raise ValueError(f"Contract file must be a YAML file: {contract_path}")

    try:
        contracts = EnhancedContractLoader.load_from_file(contract_path, allow_duplicates)

        if not contracts:
            raise ValueError(f"Contract file contains no valid contract entries: {contract_path}")

        return contracts

    except ContractConflictError as e:
        conflicts_str = "\n".join(
            [f"  - {conflict['method']} {conflict['path']} (lines: {', '.join(map(str, conflict['lines']))})"
             for conflict in e.conflicts]
        )
        raise ValueError(f"Duplicate route definitions found:\n{conflicts_str}")

    except ContractLoadError as e:
        raise ValueError(f"Error loading contract file: {e.message}\n{e.details or ''}")

    except Exception as e:
        raise ValueError(f"Unexpected error loading contract file: {str(e)}")
