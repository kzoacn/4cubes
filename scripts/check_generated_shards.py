"""Lightweight sanity checks for generated four-cubes dataset shards.

This checker verifies shard presence, boundary rows, ordering at shard
boundaries, and the exact four-cube identity for those boundary rows.  It is
intended as a quick post-generation guard; every row is already verified by
the generator before it is written.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROW_RE = re.compile(r"^(\d+)\s*=\s*(.*)$")
COEFF_RE = re.compile(r"\((-?\d+)\)\^3")


def parse_row(line: str) -> tuple[int, tuple[int, int, int, int]]:
    match = ROW_RE.match(line.strip())
    if not match:
        raise ValueError(f"bad row: {line!r}")
    n = int(match.group(1))
    xs = tuple(int(x) for x in COEFF_RE.findall(match.group(2)))
    if len(xs) != 4:
        raise ValueError(f"bad coefficient count for n={n}: {line!r}")
    return n, xs  # type: ignore[return-value]


def first_line(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        line = handle.readline()
    if not line:
        raise ValueError(f"empty shard: {path}")
    return line.rstrip("\n\r")


def last_line(path: Path) -> str:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        pos = handle.tell()
        if pos == 0:
            raise ValueError(f"empty shard: {path}")
        buf = bytearray()
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            handle.seek(pos)
            chunk = handle.read(step)
            buf[:0] = chunk
            lines = buf.splitlines()
            if len(lines) >= 2 or pos == 0:
                return lines[-1].decode("utf-8")
    raise ValueError(f"could not read last line: {path}")


def verify_identity(n: int, xs: tuple[int, int, int, int]) -> None:
    total = sum(x**3 for x in xs)
    if total != n:
        raise ValueError(f"invalid identity for n={n}: got {total}, xs={xs}")


def final_shard_index(start: int, end: int, shard_size: int) -> int:
    if end > start and end % shard_size == 0:
        return (end - 1) // shard_size
    return end // shard_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="generated/sum4cubes")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=1_000_000_000)
    parser.add_argument("--shard-size", type=int, default=10_000_000)
    args = parser.parse_args()

    out_dir = Path(args.dir)
    expected_first = args.start // args.shard_size
    expected_last = final_shard_index(args.start, args.end, args.shard_size)
    expected_count = expected_last - expected_first + 1

    shards = sorted(out_dir.glob("cubes-*.txt"))
    if len(shards) != expected_count:
        raise SystemExit(
            f"expected {expected_count} shards, found {len(shards)} in {out_dir}"
        )

    for shard_index in range(expected_first, expected_last + 1):
        path = out_dir / f"cubes-{shard_index:02d}.txt"
        if not path.exists():
            raise SystemExit(f"missing shard: {path}")

        expected_lo = max(args.start, shard_index * args.shard_size)
        if shard_index == expected_last:
            expected_hi = args.end
        else:
            expected_hi = min(args.end, (shard_index + 1) * args.shard_size - 1)

        lo_line = first_line(path)
        hi_line = last_line(path)
        lo_n, lo_xs = parse_row(lo_line)
        hi_n, hi_xs = parse_row(hi_line)
        if lo_n != expected_lo or hi_n != expected_hi:
            raise SystemExit(
                f"{path.name}: expected boundary {expected_lo}..{expected_hi}, "
                f"found {lo_n}..{hi_n}"
            )
        verify_identity(lo_n, lo_xs)
        verify_identity(hi_n, hi_xs)

    print(
        "SANITY ok "
        f"range=[{args.start},{args.end}] shards={expected_count} "
        f"dir={out_dir}"
    )


if __name__ == "__main__":
    main()
