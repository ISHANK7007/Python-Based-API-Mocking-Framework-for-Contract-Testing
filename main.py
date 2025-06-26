import argparse
from cli.cli_serve_command import handle_serve_command
from cli.cli_validate_command import handle_validate_command


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mock API framework for contract-based testing"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Add 'validate' command
    validate_parser = subparsers.add_parser("validate", help="Validate contract files")
    validate_parser.add_argument("path", type=str, help="Path to contract file or directory")
    validate_parser.set_defaults(func=handle_validate_command)

    # Add 'serve' command
    serve_parser = subparsers.add_parser("serve", help="Start the mock API server")
    serve_parser.add_argument("contract_path", type=str, help="Path to contract file or folder")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    serve_parser.add_argument("--port", type=int, default=8080, help="Server port")
    serve_parser.add_argument("--reload", action="store_true", help="Reload on file change")
    serve_parser.add_argument("--strict-validation", action="store_true", help="Enable strict mode")
    serve_parser.set_defaults(func=handle_serve_command)

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        # No subcommand was provided; show help and exit
        parser.print_help()
        exit(1)

    exit_code = args.func(args)
    exit(exit_code)


if __name__ == "__main__":
    main()
