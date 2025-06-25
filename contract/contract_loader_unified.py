from typing import Union, Dict, Any, List
from pathlib import Path

from contract.contract_entry import ContractEntry
from contract.contract_loader import ContractLoader, ContractLoadError


def load_contracts(source: Union[str, Path, Dict[str, Any]]) -> List[ContractEntry]:
    """
    Unified contract loading function that can be used by CLI, server, or other components.

    Args:
        source: Either a path to a YAML file, directory of YAML files, or a parsed dictionary

    Returns:
        List of validated ContractEntry objects

    Raises:
        ContractLoadError: If the contracts cannot be loaded or are invalid
        ValueError: If the source type is unsupported
    """
    if isinstance(source, dict):
        return ContractLoader.load_from_dict(source)

    source_path = Path(source)

    if source_path.is_dir():
        return ContractLoader.load_from_directory(source_path)
    elif source_path.is_file():
        return ContractLoader.load_from_file(source_path)
    else:
        raise ValueError(f"Unsupported source: {source}")
