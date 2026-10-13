import argparse
from rich.console import Console
from groq import Groq

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


def run_query():
    console.print('run query')

def build_parser():
    parser = argparse.ArgumentParser(
        prog="mage",
        description="Retrieval Augmented Augmented (RAG) app for the UK's Freedom of Information Code of Practice",
    )

    sub = parser.add_subparsers(dest="command")

    models = sub.add_parser("models", help="List Groq chat models you can use")
    models.set_defaults(func=run_models)

    query = sub.add_parser("query", help="Ask the generation model a question")
    query.set_defaults(func=run_query)

    return parser

def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise SystemExit(str(exc)) from exc

    args.func(settings)


if __name__ == "__main__":
    main()
