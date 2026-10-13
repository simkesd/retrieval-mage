import argparse
from rich.console import Console

console = Console()

def run_query():
    console.print('run query')

def build_parser():
    parser = argparse.ArgumentParser(
        prog="mage",
        description="Retrieval Augmented Augmented (RAG) app for the UK's Freedom of Information Code of Practice",
    )

    sub = parser.add_subparsers(dest="command")

    query = sub.add_parser("query", help="Ask the generation model a question")
    query.set_defaults(func=run_query)

    return parser

def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    console.print("Hello, World!")

    if args.command is None:
        parser.print_help()
        return
    args.func()


if __name__ == "__main__":
    main()
