import os
from contract.compatibility_checker import compatibility_check

def run_simple_check():
    old_file = "mock-v1.yaml"
    new_file = "mock-v2.yaml"

    # Ensure files exist before running
    if not os.path.exists(old_file) or not os.path.exists(new_file):
        print(f"Error: One or both contract files not found: '{old_file}', '{new_file}'")
        return

    # Run compatibility check
    try:
        is_compatible, reasons, details = compatibility_check(old_file, new_file)

        if is_compatible:
            print("✅ Contracts are compatible.")
        else:
            print("❌ Compatibility issues detected:")
            for reason in reasons:
                print(f"- {reason}")
    except Exception as e:
        print(f"Error during compatibility check: {str(e)}")

# Execute check
if __name__ == "__main__":
    run_simple_check()
