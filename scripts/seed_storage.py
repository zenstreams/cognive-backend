#!/usr/bin/env python3
"""
Seed Cognive object storage with sample objects for manual testing.

Usage (inside docker-compose api container recommended):
  python scripts/seed_storage.py
  python scripts/seed_storage.py --prefix "seed/"
  python scripts/seed_storage.py --with-urls
  python scripts/seed_storage.py --cleanup
"""

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.storage import BUCKETS, get_storage_client, init_storage  # noqa: E402


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _make_sample_files(tmpdir: Path) -> dict[str, Path]:
    """
    Create a few sample files and return named paths.
    """
    samples: dict[str, Path] = {}

    samples["hello_txt"] = tmpdir / "hello.txt"
    _write_text(samples["hello_txt"], "Hello from Cognive storage seed script.\n")

    samples["log_txt"] = tmpdir / "app.log"
    _write_text(
        samples["log_txt"],
        "2025-12-30T00:00:00Z INFO seed_storage starting\n"
        "2025-12-30T00:00:01Z INFO uploaded sample objects\n",
    )

    samples["report_csv"] = tmpdir / "report.csv"
    _write_text(samples["report_csv"], "date,cost_usd\n2025-12-30,12.34\n")

    samples["binary_bin"] = tmpdir / "blob.bin"
    _write_bytes(samples["binary_bin"], os.urandom(256))

    return samples


async def main() -> int:
    parser = argparse.ArgumentParser(description="Upload sample objects to each Cognive storage bucket.")
    parser.add_argument(
        "--prefix",
        default="seed/",
        help="Object key prefix to use (default: seed/).",
    )
    parser.add_argument(
        "--with-urls",
        action="store_true",
        help="Print a presigned URL for each uploaded object.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the uploaded objects after verifying they exist.",
    )
    parser.add_argument(
        "--expiration",
        type=int,
        default=3600,
        help="Presigned URL expiration in seconds (default: 3600).",
    )
    args = parser.parse_args()

    # Ensure buckets exist (same path used by app startup)
    await init_storage()
    storage = get_storage_client()

    uploaded: list[tuple[str, str]] = []  # (bucket, key)

    with tempfile.TemporaryDirectory(prefix="cognive-seed-") as td:
        tmpdir = Path(td)
        samples = _make_sample_files(tmpdir)

        # Map one representative file to each bucket
        mapping: dict[str, Path] = {
            "audit-logs-archive": samples["log_txt"],
            "execution-replay-data": samples["binary_bin"],
            "report-exports": samples["report_csv"],
            "agent-artifacts": samples["hello_txt"],
        }

        for bucket_name in BUCKETS.keys():
            src = mapping[bucket_name]
            key = f"{args.prefix}{bucket_name}/{src.name}"

            storage.upload_file(
                bucket_name=bucket_name,
                object_name=key,
                file_path=str(src),
                metadata={"seed": "true", "source": "scripts/seed_storage.py"},
            )

            uploaded.append((bucket_name, key))
            print(f"UPLOADED s3://{bucket_name}/{key}")

            if args.with_urls:
                url = storage.get_presigned_url(bucket_name, key, expiration=args.expiration)
                print(f"URL      {url}")

        # Basic verification by listing bucket prefixes
        print("\nVERIFY")
        for bucket_name, key in uploaded:
            prefix = key.rsplit("/", 1)[0] + "/"
            objects = storage.list_objects(bucket_name, prefix=prefix)
            ok = key in objects
            print(f"{'OK' if ok else 'MISSING'}   s3://{bucket_name}/{key}")

        if args.cleanup:
            print("\nCLEANUP")
            for bucket_name, key in uploaded:
                storage.delete_object(bucket_name, key)
                print(f"DELETED  s3://{bucket_name}/{key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))



