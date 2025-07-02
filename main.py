import argparse
import sys
import os

# Patch sys.path to ensure local imports resolve correctly
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- Safe Imports from CLI handlers ---
from cli.cli_serve_command import handle_serve_command

try:
    from cli.cli_validate_command import handle_validate_command
except ImportError:
    def handle_validate_command(args):
        print("❌ 'validate' command is currently unavailable due to import error.")
        return 1

try:
    from cli.cli_validator import handle_check_compatibility
except ImportError:
    def handle_check_compatibility(args):
        print("❌ 'check-compatibility' command is unavailable.")
        return 1

try:
    from cli.cli_json_exporter import handle_export_diff_as_json
except ImportError:
    def handle_export_diff_as_json(args):
        print("❌ 'export-json' command is unavailable.")
        return 1

try:
    from cli.cli_validator_updated import handle_enhanced_validator
except ImportError:
    def handle_enhanced_validator(args):
        print("❌ 'validate-enhanced' command is unavailable.")
        return 1

# JS-only CLI handlers (still stubbed)
def handle_replay_session(args):
    print("❌ 'replay' command is unavailable (missing cli_replay_command.py).")
    return 1

def handle_tag_session(args):
    print("❌ 'tag-session' command is unavailable (JS-only: cli_tag_command.js).")
    return 1

def handle_filter_replay(args):
    print("❌ 'filter-replay' command is unavailable (JS-only: cli_filter_support.js).")
    return 1

def handle_test_diff_scenarios(args):
    print("❌ 'test-diff-scenarios' is not implemented.")
    return 1


# --- CLI Setup ---

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mock API framework for contract-based testing")
    subparsers = parser.add_subparsers(dest="command")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate contract files")
    validate_parser.add_argument("path", type=str, help="Path to contract file or directory")
    validate_parser.set_defaults(func=handle_validate_command)

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the mock API server")
    serve_parser.add_argument("contract_path", type=str, help="Path to contract file or folder")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    serve_parser.add_argument("--port", type=int, default=8080, help="Server port")
    serve_parser.add_argument("--reload", action="store_true", help="Reload on file change")
    serve_parser.add_argument("--strict-validation", action="store_true", help="Enable strict mode")
    serve_parser.set_defaults(func=handle_serve_command)

    # check-compatibility
    compat_parser = subparsers.add_parser("check-compatibility", help="Check contract compatibility")
    compat_parser.add_argument("--from", dest="from_file", required=True, help="Source contract file")
    compat_parser.add_argument("--to", dest="to_file", required=True, help="Target contract file")
    compat_parser.add_argument("--include-non-breaking", action="store_true")
    compat_parser.add_argument("--severity", default="HIGH", choices=["HIGH", "MEDIUM", "LOW", "INFO"])
    compat_parser.add_argument("--json-output", action="store_true")
    compat_parser.add_argument("--quiet", action="store_true")
    compat_parser.set_defaults(func=handle_check_compatibility)

    # export-json
    export_parser = subparsers.add_parser("export-json", help="Export diff as JSON file")
    export_parser.add_argument("--from", dest="from_file", required=True)
    export_parser.add_argument("--to", dest="to_file", required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=handle_export_diff_as_json)

    # validate-enhanced
    enhanced_parser = subparsers.add_parser("validate-enhanced", help="Enhanced validation mode")
    enhanced_parser.add_argument("path", type=str, help="Contract file or folder")
    enhanced_parser.set_defaults(func=handle_enhanced_validator)

    # replay
    replay_parser = subparsers.add_parser("replay", help="Replay a session against a contract")
    replay_parser.add_argument("session_file", type=str)
    replay_parser.add_argument("--contract", required=True)
    replay_parser.add_argument("--strict", action="store_true")
    replay_parser.set_defaults(func=handle_replay_session)

    # tag-session
    tag_parser = subparsers.add_parser("tag-session", help="Add metadata tags to a session")
    tag_parser.add_argument("session_file", type=str)
    tag_parser.add_argument("--tags", required=True)
    tag_parser.set_defaults(func=handle_tag_session)

    # filter-replay
    filter_parser = subparsers.add_parser("filter-replay", help="Replay sessions with filtering")
    filter_parser.add_argument("session_file", type=str)
    filter_parser.add_argument("--method", help="HTTP method to filter by")
    filter_parser.add_argument("--route", help="Route or path regex")
    filter_parser.set_defaults(func=handle_filter_replay)

    # test-diff-scenarios
    test_parser = subparsers.add_parser("test-diff-scenarios", help="Run or generate test scenarios for diffing")
    test_parser.add_argument("--create", action="store_true", help="Create example contracts for diff testing")
    test_parser.set_defaults(func=handle_test_diff_scenarios)

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)

    exit_code = args.func(args)
    exit(exit_code)


if __name__ == "__main__":
    main()
