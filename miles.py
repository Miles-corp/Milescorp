#!/usr/bin/env python3
"""MILES — Assistant personnel intelligent. Point d'entrée du programme."""

import sys
import argparse

from app.config.settings import Settings
from app.interface.cli import CLI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miles",
        description="MILES — Assistant personnel intelligent (prototype)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Chemin vers le fichier de configuration JSON (par défaut: config/config.json ou variables d'environnement)",
    )
    parser.add_argument(
        "--provider",
        choices=["remote", "local"],
        default=None,
        help="Fournisseur IA à utiliser (remplace la configuration)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings(config_path=args.config)
    except Exception as exc:  # noqa: BLE001 — erreur de configuration fatale
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        print("Consultez config/config.json.example et .env.example.", file=sys.stderr)
        return 1

    if args.provider is not None:
        settings.provider = args.provider

    cli = CLI(settings=settings)
    try:
        cli.run()
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur. Au revoir !")
        return 0
    except EOFError:
        print("\nFin de saisie. Au revoir !")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
