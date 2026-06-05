"""Generate HuggingFace-style four-cubes certificate shards in parallel.

Run a small test with:
    sage -python scripts/generate_hf_dataset.py --end 1000 --workers 15 \
        --chunk-size 50 --out-dir analysis/mp_test_cubes --overwrite

A full local generation uses the same format as the current dataset:
    sage -python scripts/generate_hf_dataset.py --start 0 --end 1000000000 \
        --workers 15 --out-dir generated/sum4cubes --overwrite \
        --merge-final-singleton

Resume from a shard boundary after an interrupted run:
    sage -python scripts/generate_hf_dataset.py --start 80000000 \
        --end 1000000000 --workers 15 --out-dir generated/sum4cubes \
        --resume

The parent process keeps output ordered while bounding the number of chunks
in flight, so a slow early chunk cannot make completed later chunks accumulate
without limit in memory.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path

from sage.all import ZZ

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import four_cubes_reference as ref


_SOLVER_LIMIT = 10**8


def _init_worker(solver_limit):
    global _SOLVER_LIMIT
    _SOLVER_LIMIT = solver_limit


def _format_row(n, xs):
    x1, x2, x3, x4 = xs
    return f"{n} = ({x1})^3 + ({x2})^3 + ({x3})^3 + ({x4})^3\n"


def _solve_one(n):
    sol = ref.solve(ZZ(n), limit=_SOLVER_LIMIT, return_d=True)
    if sol is None:
        raise RuntimeError(f"no solution found for n={n}")
    xs = tuple(ZZ(x) for x in sol[:4])
    d = ZZ(sol[4])
    if not ref.verify(ZZ(n), xs):
        raise RuntimeError(f"invalid identity for n={n}: {xs}")
    h = max(abs(x) for x in xs)
    return _format_row(n, xs), int(d), int(h)


def _worker_range(task):
    start, end = task
    t0 = time.monotonic()
    rows = []
    max_d = 0
    max_h = 0
    max_d_n = start
    max_h_n = start
    for n in range(start, end + 1):
        row, d, h = _solve_one(n)
        rows.append(row)
        if d > max_d:
            max_d = d
            max_d_n = n
        if h > max_h:
            max_h = h
            max_h_n = n
    return {
        "start": start,
        "end": end,
        "rows": rows,
        "count": end - start + 1,
        "max_d": max_d,
        "max_d_n": max_d_n,
        "max_h": max_h,
        "max_h_n": max_h_n,
        "elapsed": time.monotonic() - t0,
    }


def _iter_tasks(start, end, chunk_size):
    cur = start
    while cur <= end:
        hi = min(cur + chunk_size - 1, end)
        yield (cur, hi)
        cur = hi + 1


def _shard_path(out_dir, shard_index):
    return out_dir / f"cubes-{shard_index:02d}.txt"


def _last_shard_index(start, end, shard_size, merge_final_singleton):
    if merge_final_singleton and end > start and end % shard_size == 0:
        return (end - 1) // shard_size
    return end // shard_size


def _last_line(path):
    with path.open("rb") as handle:
        handle.seek(0, 2)
        pos = handle.tell()
        if pos == 0:
            raise RuntimeError(f"empty shard {path}")
        buf = bytearray()
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            handle.seek(pos)
            buf[:0] = handle.read(step)
            lines = buf.splitlines()
            if len(lines) >= 2 or pos == 0:
                return lines[-1].decode("utf-8")
    raise RuntimeError(f"could not read last line from {path}")


def _merge_final_singleton(out_dir, start, end, shard_size):
    if end <= start or end % shard_size != 0:
        return False
    final_index = end // shard_size
    previous_index = final_index - 1
    final_path = _shard_path(out_dir, final_index)
    previous_path = _shard_path(out_dir, previous_index)
    if not final_path.exists():
        return False
    if not previous_path.exists():
        raise RuntimeError(f"missing previous shard {previous_path}")

    text = final_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) != 1:
        raise RuntimeError(f"expected singleton shard {final_path}, found {len(lines)} rows")
    n, _ = _parse_row(lines[0])
    if n != end:
        raise RuntimeError(f"expected final row n={end}, found n={n}")

    prev_n, _ = _parse_row(_last_line(previous_path))
    if prev_n == end:
        final_path.unlink()
        return True

    with previous_path.open("a", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")
    final_path.unlink()
    return True


class ShardWriter:
    def __init__(self, out_dir, shard_size):
        self.out_dir = out_dir
        self.shard_size = shard_size
        self.current_index = None
        self.handle = None

    def write_rows(self, start, rows):
        for offset, row in enumerate(rows):
            n = start + offset
            shard_index = n // self.shard_size
            if shard_index != self.current_index:
                self.close()
                self.current_index = shard_index
                path = _shard_path(self.out_dir, shard_index)
                self.handle = path.open("a", encoding="utf-8")
            self.handle.write(row)

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def _prepare_out_dir(out_dir, overwrite, resume):
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("cubes-*.txt"))
    if overwrite and resume:
        raise SystemExit("use at most one of --overwrite and --resume")
    if resume:
        return
    if existing and not overwrite:
        sample = ", ".join(p.name for p in existing[:3])
        raise SystemExit(
            f"{out_dir} already contains cubes shards ({sample}); "
            "pass --overwrite to replace them or --resume to append from --start"
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _parse_row(line):
    m = re.match(r"^(\d+)\s*=\s*(.*)$", line.strip())
    if not m:
        raise ValueError(f"bad row: {line!r}")
    n = int(m.group(1))
    xs = tuple(int(x) for x in re.findall(r"\((-?\d+)\)\^3", m.group(2)))
    if len(xs) != 4:
        raise ValueError(f"bad coefficient count for n={n}")
    return n, xs


def verify_generated(out_dir, start, end, shard_size, merge_final_singleton=False):
    expected = start
    total = 0
    last_shard = _last_shard_index(start, end, shard_size, merge_final_singleton)
    for shard_index in range(start // shard_size, last_shard + 1):
        path = _shard_path(out_dir, shard_index)
        if not path.exists():
            raise RuntimeError(f"missing shard {path}")
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                n, xs = _parse_row(line)
                if n < start or n > end:
                    continue
                if n != expected:
                    raise RuntimeError(f"expected n={expected}, found n={n}")
                if sum(ZZ(x) ** 3 for x in xs) != ZZ(n):
                    raise RuntimeError(f"invalid identity for n={n}: {xs}")
                expected += 1
                total += 1
    if expected != end + 1:
        raise RuntimeError(f"stopped at n={expected}, expected {end + 1}")
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=1_000_000_000)
    parser.add_argument("--workers", type=int, default=15)
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument(
        "--max-in-flight",
        type=int,
        default=0,
        help="maximum submitted chunks; default is 4*workers",
    )
    parser.add_argument("--shard-size", type=int, default=10_000_000)
    parser.add_argument("--solver-limit", type=int, default=10**8)
    parser.add_argument("--out-dir", default="generated/sum4cubes")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="keep existing shards and continue writing from --start",
    )
    parser.add_argument("--verify-output", action="store_true")
    parser.add_argument(
        "--merge-final-singleton",
        action="store_true",
        help="if --end falls on a shard boundary, append that singleton row "
        "to the previous shard",
    )
    parser.add_argument("--progress-every", type=int, default=100_000)
    args = parser.parse_args()

    if args.start < 0 or args.end < args.start:
        raise SystemExit("require 0 <= start <= end")
    if args.workers < 1:
        raise SystemExit("--workers must be positive")
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be positive")
    if args.shard_size < 1:
        raise SystemExit("--shard-size must be positive")
    max_in_flight = args.max_in_flight or 4 * args.workers
    if max_in_flight < args.workers:
        raise SystemExit("--max-in-flight must be at least --workers")

    out_dir = Path(args.out_dir)
    _prepare_out_dir(out_dir, args.overwrite, args.resume)

    total_expected = args.end - args.start + 1
    task_iter = iter(_iter_tasks(args.start, args.end, args.chunk_size))
    writer = ShardWriter(out_dir, args.shard_size)

    print(
        "START "
        f"range=[{args.start},{args.end}] rows={total_expected} "
        f"workers={args.workers} chunk_size={args.chunk_size} "
        f"max_in_flight={max_in_flight} "
        f"shard_size={args.shard_size} out_dir={out_dir}",
        flush=True,
    )

    start_time = time.monotonic()
    processed = 0
    next_progress = args.progress_every if args.progress_every else None
    global_max_d = (0, args.start)
    global_max_h = (0, args.start)

    try:
        ctx = mp.get_context("fork")
    except ValueError:
        ctx = mp.get_context()

    def handle_result(result):
        nonlocal processed, next_progress, global_max_d, global_max_h
        writer.write_rows(result["start"], result["rows"])
        processed += result["count"]

        if result["max_d"] > global_max_d[0]:
            global_max_d = (result["max_d"], result["max_d_n"])
        if result["max_h"] > global_max_h[0]:
            global_max_h = (result["max_h"], result["max_h_n"])

        if next_progress is not None and processed >= next_progress:
            elapsed = time.monotonic() - start_time
            print(
                "PROGRESS "
                f"rows={processed}/{total_expected} "
                f"last_n={result['end']} "
                f"rate={processed / elapsed:.2f}/s "
                f"chunk_elapsed={result['elapsed']:.2f}s "
                f"max_d={global_max_d[0]}@{global_max_d[1]}",
                flush=True,
            )
            while next_progress is not None and processed >= next_progress:
                next_progress += args.progress_every

    with ctx.Pool(
        processes=args.workers,
        initializer=_init_worker,
        initargs=(args.solver_limit,),
    ) as pool:
        in_flight = {}
        exhausted = False

        def submit_until_full():
            nonlocal exhausted
            while not exhausted and len(in_flight) < max_in_flight:
                try:
                    task = next(task_iter)
                except StopIteration:
                    exhausted = True
                    return
                in_flight[task[0]] = pool.apply_async(_worker_range, (task,))

        try:
            submit_until_full()
            next_start = args.start
            while in_flight:
                async_result = in_flight.pop(next_start)
                result = async_result.get()
                if result["start"] != next_start:
                    raise RuntimeError(
                        f"internal ordering error: expected {next_start}, "
                        f"got {result['start']}"
                    )
                handle_result(result)
                next_start = result["end"] + 1
                submit_until_full()
        finally:
            writer.close()

    elapsed = time.monotonic() - start_time
    print(
        "DONE "
        f"rows={processed} elapsed={elapsed:.6f}s "
        f"rate={processed / elapsed if elapsed else 0.0:.6f}/s "
        f"max_d={global_max_d[0]}@{global_max_d[1]} "
        f"max_h={global_max_h[0]}@{global_max_h[1]}",
        flush=True,
    )

    if args.merge_final_singleton:
        if _merge_final_singleton(out_dir, args.start, args.end, args.shard_size):
            print("MERGE_FINAL_SINGLETON ok", flush=True)

    if args.verify_output:
        checked = verify_generated(
            out_dir,
            args.start,
            args.end,
            args.shard_size,
            args.merge_final_singleton,
        )
        print(f"VERIFY ok rows={checked}", flush=True)


if __name__ == "__main__":
    main()
