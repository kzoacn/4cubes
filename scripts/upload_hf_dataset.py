"""Upload four-cubes dataset files to Hugging Face.

Set HF_TOKEN in the environment before running.  The script uploads the
current generator/checker scripts and, optionally, all data shards.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from huggingface_hub import HfApi


DEFAULT_CODE_FILES = [
    Path("README.md"),
    Path("scripts/four_cubes_reference.py"),
    Path("scripts/generate_hf_dataset.py"),
    Path("scripts/check_generated_shards.py"),
    Path("scripts/upload_hf_dataset.py"),
]


def upload_with_retries(api, *, retries: int, **kwargs) -> None:
    for attempt in range(1, retries + 1):
        try:
            api.upload_file(**kwargs)
            return
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(60, 5 * attempt))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="kzoacn/sum4cubes")
    parser.add_argument("--repo-type", default="dataset")
    parser.add_argument("--data-dir", default="generated/sum4cubes")
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--end-shard", type=int, default=99)
    parser.add_argument("--skip-data", action="store_true")
    parser.add_argument("--skip-code", action="store_true")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token and not args.dry_run:
        raise SystemExit("HF_TOKEN is not set")

    api = HfApi(token=token)
    uploads: list[tuple[Path, str, str]] = []

    if not args.skip_code:
        for path in DEFAULT_CODE_FILES:
            uploads.append((path, str(path), "Upload generation and checking scripts"))

    if not args.skip_data:
        data_dir = Path(args.data_dir)
        for shard in range(args.start_shard, args.end_shard + 1):
            path = data_dir / f"cubes-{shard:02d}.txt"
            uploads.append((path, path.name, f"Upload four-cubes shard {shard:02d}"))

    for path, path_in_repo, message in uploads:
        if not path.exists():
            raise SystemExit(f"missing local file: {path}")
        size = path.stat().st_size
        print(f"UPLOAD {path} -> {path_in_repo} bytes={size}", flush=True)
        if args.dry_run:
            continue
        upload_with_retries(
            api,
            retries=args.retries,
            path_or_fileobj=str(path),
            path_in_repo=path_in_repo,
            repo_id=args.repo_id,
            repo_type=args.repo_type,
            commit_message=message,
        )
        print(f"DONE {path_in_repo}", flush=True)


if __name__ == "__main__":
    main()
