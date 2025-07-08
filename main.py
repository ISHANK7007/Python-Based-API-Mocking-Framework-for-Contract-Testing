import argparse
import sys
import os

# Patch sys.path for local imports
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- Safe Imports from CLI handlers ---
from cli.cli_serve_command import handle_serve_command

try:
    from cli.cli_validate_command import handle_validate_command
except ImportError:
    def handle_validate_command(args):
        print("❌ 'validate' command is currently unavailable.")
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

try:
    from cli.cli_diff_command import handle_diff_command
except ImportError:
    def handle_diff_command(args):
        print("❌ 'diff' command is unavailable.")
        return 1

try:
    from cli.cli_chaos_flags import apply_chaos_cli_overrides
except ImportError:
    def apply_chaos_cli_overrides(args, config):
        print("⚠️  Chaos CLI override support not available.")
        return config

try:
    from cli.cli_report_compare import compare_reports as handle_report_compare
except ImportError:
    def handle_report_compare(args):
        print("❌ 'report compare' command is unavailable.")
        return 1

# JS-only CLI handlers
def handle_replay_session(args):
    print("❌ 'replay' command is unavailable (JS-only).")
    return 1

def handle_tag_session(args):
    print("❌ 'tag-session' command is unavailable (JS-only).")
    return 1

def handle_filter_replay(args):
    print("❌ 'filter-replay' command is unavailable (JS-only).")
    return 1

def handle_test_diff_scenarios(args):
    print("❌ 'test-diff-scenarios' is not implemented.")
    return 1

# --- CLI Setup ---
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="🔧 MockAPI: Contract-Based Testing & Simulation Framework",
        epilog="""Examples:
  mockapi validate contracts.yaml
  mockapi serve ./contracts --chaos-seed 42
  mockapi diff v1.yaml v2.yaml --format json
  mockapi report-compare v1.json v2.json --summary-only

Docs: https://github.com/your-org/mockapi
Contact: dev-team@example.com""",
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="Available Commands",
        metavar="{validate, serve, diff, ...}"
    )

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate contract files")
    validate_parser.add_argument("path", type=str, help="Path to contract file or directory")
    validate_parser.set_defaults(func=handle_validate_command)

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the mock API server with chaos/test support")
    serve_parser.add_argument("contract_path", type=str)
    serve_parser.add_argument("--host", type=str, default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--strict-validation", action="store_true")
    serve_parser.add_argument("--chaos-seed", type=int)
    serve_parser.add_argument("--force-delay", nargs='*')
    serve_parser.add_argument("--force-error", nargs='*')
    serve_parser.set_defaults(func=handle_serve_command)

    # check-compatibility
    compat_parser = subparsers.add_parser("check-compatibility", help="Compare old/new contracts for breaking changes")
    compat_parser.add_argument("--from", dest="from_file", required=True)
    compat_parser.add_argument("--to", dest="to_file", required=True)
    compat_parser.add_argument("--include-non-breaking", action="store_true")
    compat_parser.add_argument("--severity", default="HIGH", choices=["HIGH", "MEDIUM", "LOW", "INFO"])
    compat_parser.add_argument("--json-output", action="store_true")
    compat_parser.add_argument("--quiet", action="store_true")
    compat_parser.set_defaults(func=handle_check_compatibility)

    # export-json
    export_parser = subparsers.add_parser("export-json", help="Output a structured diff as JSON")
    export_parser.add_argument("--from", dest="from_file", required=True)
    export_parser.add_argument("--to", dest="to_file", required=True)
    export_parser.add_argument("--output", required=True)
    export_parser.set_defaults(func=handle_export_diff_as_json)

    # validate-enhanced
    enhanced_parser = subparsers.add_parser("validate-enhanced", help="Run strict validation using schema + filters")
    enhanced_parser.add_argument("path", type=str)
    enhanced_parser.set_defaults(func=handle_enhanced_validator)

    # diff
    diff_parser = subparsers.add_parser("diff", help="Summarize contract drift between versions")
    diff_parser.add_argument("base", help="Base contract YAML file")
    diff_parser.add_argument("target", help="Target contract YAML file")
    diff_parser.add_argument("--format", choices=["table", "json"], default="table")
    diff_parser.add_argument("--check-deprecated", action="store_true")
    diff_parser.add_argument("--deprecation-report", action="store_true")
    diff_parser.add_argument("--import-usage-data")
    diff_parser.add_argument("--deprecation-exit-code", action="store_true")
    diff_parser.set_defaults(func=handle_diff_command)

    # report-compare
    compare_parser = subparsers.add_parser("report-compare", help="Compare historical report files (HTML, JSON, Markdown)")
    compare_parser.add_argument("base_report")
    compare_parser.add_argument("current_report")
    compare_parser.add_argument("--format", choices=["html", "markdown", "json", "terminal"], default="terminal")
    compare_parser.add_argument("--output")
    compare_parser.add_argument("--focus", nargs='*', choices=["coverage", "chaos", "contract", "performance"])
    compare_parser.add_argument("--threshold", type=float, default=5.0)
    compare_parser.add_argument("--include-improved", action="store_true", default=True)
    compare_parser.add_argument("--summary-only", action="store_true")
    compare_parser.set_defaults(func=handle_report_compare)

    # JS-only commands
    replay_parser = subparsers.add_parser("replay", help="Replay a session against a contract (JS-only)")
    replay_parser.add_argument("session_file", type=str)
    replay_parser.add_argument("--contract", required=True)
    replay_parser.add_argument("--strict", action="store_true")
    replay_parser.set_defaults(func=handle_replay_session)

    tag_parser = subparsers.add_parser("tag-session", help="Add metadata tags to a session (JS-only)")
    tag_parser.add_argument("session_file", type=str)
    tag_parser.add_argument("--tags", required=True)
    tag_parser.set_defaults(func=handle_tag_session)

    filter_parser = subparsers.add_parser("filter-replay", help="Replay sessions with filtering (JS-only)")
    filter_parser.add_argument("session_file", type=str)
    filter_parser.add_argument("--method")
    filter_parser.add_argument("--route")
    filter_parser.set_defaults(func=handle_filter_replay)

    test_parser = subparsers.add_parser("test-diff-scenarios", help="Run or generate test scenarios for diffing")
    test_parser.add_argument("--create", action="store_true")
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