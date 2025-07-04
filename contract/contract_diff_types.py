from contract.contract_version_manager import ContractVersionManager
from contract.contract_entry import ContractEntry


def main() -> None:
    # Initialize the version manager
    manager = ContractVersionManager()
    
    # Discover all contract versions in the directory
    contracts_dir = './contracts'
    manager.discover_contracts(contracts_dir)

    contract_names = list(manager.versions.keys())
    print(f"\n✅ Discovered contracts: {contract_names}")

    for contract_name in contract_names:
        print(f"\n📘 Processing contract: {contract_name}")

        # Get latest version
        latest = manager.get_latest_version(contract_name)
        if not latest:
            print(f"⚠️  No versions found for {contract_name}")
            continue

        print(f"🔖 Latest version: {latest.version}")

        try:
            # Build comparison history across all versions
            baseline = manager.build_comparison_baseline(contract_name)

            # Display version metadata
            print("📜 Version history:")
            for v in baseline['version_details']:
                print(f"  - {v['version']} (File: {v['file_path']}, Released: {v['release_date']})")

            # Show diff summaries
            print("🔄 Change history between versions:")
            for comp in baseline['comparisons']:
                print(f"  ↪ From {comp['from_version']} → {comp['to_version']}")
                changes = comp['changes']
                if changes['added_routes']:
                    print(f"    ➕ {len(changes['added_routes'])} route(s) added")
                if changes['removed_routes']:
                    print(f"    ➖ {len(changes['removed_routes'])} route(s) removed")
                if changes['modified_routes']:
                    print(f"    ✏️  {len(changes['modified_routes'])} route(s) modified")

            # Load latest contract object
            contract: ContractEntry = manager.load_contract(latest)
            print(f"✅ Loaded latest contract with {len(contract.routes)} route(s)")

        except ValueError as e:
            print(f"❌ Error processing {contract_name}: {e}")


if __name__ == "__main__":
    main()
