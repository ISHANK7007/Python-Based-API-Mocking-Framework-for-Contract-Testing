
import os
import glob
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from contract.contract_version import ContractVersion
from contract.contract_loader import ContractLoader
from contract.contract_entry import ContractEntry


class ContractVersionManager:
    """
    Manages multiple versions of contract files and facilitates comparison.
    Uses the existing ContractLoader to load the contracts.
    """
    def __init__(self):
        self.versions: Dict[str, List[ContractVersion]] = defaultdict(list)
        self.contract_cache: Dict[str, ContractEntry] = {}

    def discover_contracts(self, directory: str) -> None:
        pattern = os.path.join(directory, "*.yaml")
        for file_path in glob.glob(pattern):
            try:
                version = ContractVersion.from_file_path(file_path)
                self.versions[version.name].append(version)
            except ValueError:
                continue

        for version_list in self.versions.values():
            version_list.sort()

    def get_latest_version(self, contract_name: str) -> Optional[ContractVersion]:
        versions = self.versions.get(contract_name, [])
        return versions[-1] if versions else None

    def get_version(self, contract_name: str, version_str: str) -> Optional[ContractVersion]:
        canonical = f"v{version_str}"
        for version in self.versions.get(contract_name, []):
            if version.version == canonical:
                return version
        return None

    def load_contract(self, version: ContractVersion) -> ContractEntry:
        if version.file_path not in self.contract_cache:
            loader = ContractLoader()
            contract = loader.load(version.file_path)
            contract.metadata['version'] = version.version
            contract.metadata['contract_name'] = version.name
            contract.metadata['release_date'] = version.release_date.isoformat() if version.release_date else None
            self.contract_cache[version.file_path] = contract
        return self.contract_cache[version.file_path]

    def compare_versions(self, contract_name: str, version1_str: str, version2_str: str) -> dict:
        v1 = self.get_version(contract_name, version1_str)
        v2 = self.get_version(contract_name, version2_str)

        if not v1 or not v2:
            raise ValueError(f"One or both versions not found: {version1_str}, {version2_str}")

        contract1 = self.load_contract(v1)
        contract2 = self.load_contract(v2)

        routes1 = {route.path: route for route in contract1.routes}
        routes2 = {route.path: route for route in contract2.routes}

        added_routes = set(routes2) - set(routes1)
        removed_routes = set(routes1) - set(routes2)
        common_routes = set(routes1) & set(routes2)

        modified_routes = []
        for path in common_routes:
            r1, r2 = routes1[path], routes2[path]
            if (r1.method != r2.method or
                r1.request_schema != r2.request_schema or
                r1.responses != r2.responses):
                modified_routes.append({
                    'path': path,
                    'changes': self._identify_route_changes(r1, r2)
                })

        return {
            'version1': str(v1),
            'version2': str(v2),
            'added_routes': list(added_routes),
            'removed_routes': list(removed_routes),
            'modified_routes': modified_routes
        }

    def _identify_route_changes(self, route1, route2) -> dict:
        changes = {}

        if route1.method != route2.method:
            changes['method'] = {'from': route1.method, 'to': route2.method}

        if route1.request_schema != route2.request_schema:
            changes['request_schema'] = {'changed': True}

        if route1.responses != route2.responses:
            codes1 = {r.status_code for r in route1.responses}
            codes2 = {r.status_code for r in route2.responses}
            changes['responses'] = {
                'added_status_codes': list(codes2 - codes1),
                'removed_status_codes': list(codes1 - codes2)
            }

        return changes

    def build_comparison_baseline(self, contract_name: str) -> dict:
        versions = self.versions.get(contract_name, [])
        if not versions:
            raise ValueError(f"No versions found for contract: {contract_name}")

        versions.sort()

        comparisons = []
        for i in range(1, len(versions)):
            v1, v2 = versions[i - 1], versions[i]
            diff = self.compare_versions(contract_name, v1.version.lstrip("v"), v2.version.lstrip("v"))
            comparisons.append({
                'from_version': v1.version,
                'to_version': v2.version,
                'changes': diff
            })

        return {
            'contract_name': contract_name,
            'versions': [v.version for v in versions],
            'version_details': [
                {
                    'version': v.version,
                    'file_path': v.file_path,
                    'release_date': v.release_date.isoformat() if v.release_date else None
                } for v in versions
            ],
            'comparisons': comparisons,
            'latest_version': versions[-1].version
        }
