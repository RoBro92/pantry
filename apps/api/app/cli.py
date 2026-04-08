from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.db import SessionLocal
from app.services.development_seed import DEV_MODE_CHOICES, bootstrap_development_mode
from app.services.auth import count_platform_admins, create_platform_admin, reset_user_password
from app.services.e2e_seed import seed_e2e_baseline
from app.services.setup import mark_setup_completed


def _load_password(value: str | None, prompt_text: str) -> str:
    password = value or getpass(prompt_text)
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")
    return password


def _run_migrations() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    command.upgrade(config, "head")


def bootstrap_platform_admin(args: argparse.Namespace) -> None:
    _run_migrations()
    password = _load_password(args.password, "Platform admin password: ")

    with SessionLocal() as db:
        if count_platform_admins(db) > 0:
            raise SystemExit("A platform admin already exists. Use application flows for additional setup.")

        user = create_platform_admin(
            db,
            email=args.email,
            password=password,
            display_name=args.display_name,
        )
        mark_setup_completed(db)
        print(f"Created platform admin {user.email} ({user.external_id})")


def reset_password(args: argparse.Namespace) -> None:
    _run_migrations()
    password = _load_password(args.password, "New password: ")

    with SessionLocal() as db:
        user = reset_user_password(db, email=args.email, password=password)
        print(f"Reset password for {user.email} ({user.external_id})")


def seed_e2e(args: argparse.Namespace) -> None:
    _run_migrations()

    with SessionLocal() as db:
        manifest = seed_e2e_baseline(db)

    if getattr(args, "json_output", False):
        print(manifest.to_json())
        return

    print("Seeded deterministic E2E baseline.")
    print(manifest.to_json())


def seed_development_mode(args: argparse.Namespace) -> None:
    _run_migrations()

    with SessionLocal() as db:
        manifest = bootstrap_development_mode(db, mode=args.mode)

    if getattr(args, "json_output", False):
        print(manifest.to_json())
        return

    print(f"Prepared local development mode: {manifest.mode}.")
    print(manifest.to_json())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pantry API operational commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap-platform-admin", help="Create the first platform admin user."
    )
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.add_argument("--display-name")
    bootstrap_parser.add_argument("--password")
    bootstrap_parser.set_defaults(func=bootstrap_platform_admin)

    reset_parser = subparsers.add_parser("reset-password", help="Reset the password for an existing user.")
    reset_parser.add_argument("--email", required=True)
    reset_parser.add_argument("--password")
    reset_parser.set_defaults(func=reset_password)

    seed_parser = subparsers.add_parser(
        "seed-e2e",
        help="Reset application data and seed the deterministic E2E baseline.",
    )
    seed_parser.add_argument("--json", action="store_true", dest="json_output")
    seed_parser.set_defaults(func=seed_e2e)

    development_seed_parser = subparsers.add_parser(
        "seed-development-mode",
        help="Reset the local development database into an explicit fresh or demo mode.",
    )
    development_seed_parser.add_argument("--mode", required=True, choices=DEV_MODE_CHOICES)
    development_seed_parser.add_argument("--json", action="store_true", dest="json_output")
    development_seed_parser.set_defaults(func=seed_development_mode)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
