"""Trusted local operator CLI for managing one-time spending authorizations.

This module is intentionally not exposed as an agent-facing HTTP endpoint.
Only run it in a trusted operator environment with access to the SQLite database.
"""
import argparse
import getpass
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from app.store import SQLiteStore


def _positive_minutes(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a whole number of minutes") from exc
    if minutes <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return minutes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trusted operator interface for spending authorizations."
    )
    parser.add_argument(
        "--db", default="data/guardrail.db",
        help="SQLite database path (default: data/guardrail.db)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create a one-time spending authorization")
    create.add_argument("--authorization-id", required=True)
    create.add_argument("--agent-id", required=True)
    create.add_argument("--recipient", required=True)
    create.add_argument("--max-amount", required=True)
    create.add_argument("--asset", default="NEAR")
    create.add_argument("--network", default="testnet")
    create.add_argument("--expires-in-minutes", type=_positive_minutes, default=15)
    create.add_argument("--created-by", default=f"operator:{getpass.getuser()}")
    create.set_defaults(handler=_create)

    listing = commands.add_parser("list", help="List authorization records and their status")
    listing.set_defaults(handler=_list)

    revoke = commands.add_parser("revoke", help="Revoke an unused authorization")
    revoke.add_argument("authorization_id")
    revoke.set_defaults(handler=_revoke)
    return parser


def _create(args: argparse.Namespace, store: SQLiteStore) -> int:
    try:
        amount = Decimal(args.max_amount)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=args.expires_in_minutes)
        created = store.create_authorization(
            authorization_id=args.authorization_id.strip(),
            agent_id=args.agent_id.strip(),
            recipient=args.recipient.strip(),
            max_amount=amount,
            asset=args.asset.strip().upper(),
            network=args.network.strip().lower(),
            expires_at=expiry.isoformat(),
            created_by=args.created_by.strip(),
        )
    except (InvalidOperation, ValueError) as exc:
        print(f"Invalid authorization: {exc}", file=sys.stderr)
        return 2

    if not created:
        print("Authorization ID already exists; choose a new unique ID.", file=sys.stderr)
        return 1
    print(f"Created authorization {args.authorization_id} (expires {expiry.isoformat()}).")
    print("This authorization is single-use and cannot be expanded by the agent.")
    return 0


def _list(args: argparse.Namespace, store: SQLiteStore) -> int:
    records = store.list_authorizations()
    if not records:
        print("No authorizations found.")
        return 0

    now = datetime.now(timezone.utc)
    print("ID | AGENT | RECIPIENT | LIMIT | ASSET/NETWORK | STATUS | EXPIRES")
    for item in records:
        expiry = datetime.fromisoformat(item["expires_at"])
        if item["revoked_at"]:
            status = "REVOKED"
        elif item["consumed_at"]:
            status = "CONSUMED"
        elif expiry <= now:
            status = "EXPIRED"
        else:
            status = "ACTIVE"
        print(
            f"{item['authorization_id']} | {item['agent_id']} | {item['recipient']} | "
            f"{item['max_amount']} | {item['asset']}/{item['network']} | {status} | "
            f"{item['expires_at']}"
        )
    return 0


def _revoke(args: argparse.Namespace, store: SQLiteStore) -> int:
    if store.revoke_authorization(args.authorization_id):
        print(f"Revoked authorization {args.authorization_id}.")
        return 0
    print(
        "Could not revoke: authorization was not found, already revoked, or already consumed.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        store = SQLiteStore(args.db)
        return args.handler(args, store)
    except (OSError, ValueError) as exc:
        print(f"Operator CLI error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
