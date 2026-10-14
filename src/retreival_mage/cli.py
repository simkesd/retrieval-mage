import argparse
from rich.console import Console
from groq import Groq

from retreival_mage.corpus import CORPUS_PATH, CorpusError, setup_corpus
from retreival_mage.extract import extract
from retreival_mage.settings import ConfigError, Settings

console = Console()

def is_chat_model(model_id: str) -> bool:
    non_chat_models = ("whisper", "tts", "guard", "embed", "distil-whisper")
    lowered = model_id.lower()
    return not any(tag in lowered for tag in non_chat_models)

def run_models(settings):
    client = Groq(api_key=settings.groq_api_key)

    models = client.models.list()
    sorted_models = sorted(m.id for m in models.data if is_chat_model(m.id))

    console.print(f"[bold]{len(sorted_models)} chat models available[/bold]")

    console.print()
    for model_id in sorted_models:
        if model_id == settings.generation_model:
            console.print(f"  {model_id}  [green]<- current GENERATION_MODEL[/green]")
        else:
            console.print(f"  {model_id}")
    if settings.generation_model not in sorted_models:
        raise SystemExit(
            f"Current GENERATION_MODEL ({settings.generation_model!r}) "
            "is not in the list above."
        )


def run_query(settings):
    console.print(f"run query ({settings.generation_model})")

def run_extract(file_location):
    raw_path, clean_path = extract(file_location)
    console.print(f"[green]Extracted text:[/green] {raw_path}")
    console.print(f"[green]Cleaned text:[/green] {clean_path}")


def run_setup():
    try:
        status = setup_corpus()
    except CorpusError as exc:
        raise SystemExit(str(exc)) from exc

    if status == "present":
        console.print(f"[green]Code of Practice already present:[/green] {CORPUS_PATH}")
    else:
        console.print(f"[green]Downloaded Code of Practice:[/green] {CORPUS_PATH}")

def build_parser():
    parser = argparse.ArgumentParser(
        prog="mage",
        description="Retrieval Augmented Augmented (RAG) app for the UK's Freedom of Information Code of Practice",
    )

    sub = parser.add_subparsers(dest="command")

    models = sub.add_parser("models", help="List Groq chat models you can use")
    models.set_defaults(func=run_models, needs_settings=True)

    query = sub.add_parser("query", help="Ask the generation model a question")
    query.set_defaults(func=run_query, needs_settings=True)

    setup = sub.add_parser(
        "setup",
        help="Download the Freedom of Information Code of Practice if it is missing",
    )
    setup.set_defaults(func=run_setup, needs_settings=False)

    extract_cmd = sub.add_parser(
        "extract",
        help="Extract a PDF into a raw text file and then process it and create a new cleaned file.",
    )
    extract_cmd.add_argument(
        "file_location",
        nargs="?",
        default=CORPUS_PATH,
        help=f"Path to a PDF to extract (default: {CORPUS_PATH})",
    )
    extract_cmd.set_defaults(func=run_extract, needs_settings=False)

    return parser

def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    if not args.needs_settings:
        if args.command == "extract":
            args.func(args.file_location)
        else:
            args.func()
        return

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc

    args.func(settings)


if __name__ == "__main__":
    main()
