"""Compare the reference solver with the HuggingFace certificate file.

This script streams the HuggingFace text file and does not store it locally.

Run with:
    sage -python scripts/compare_hf_reference.py --limit 1000
"""

import argparse
import importlib.util
import re
import time
from urllib.request import urlopen

HF_URL = "https://huggingface.co/datasets/kzoacn/sum4cubes/resolve/main/cubes-00.txt"


def load_reference_module():
    spec = importlib.util.spec_from_file_location(
        "four_cubes_reference", "scripts/four_cubes_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_hf_rows(limit):
    with urlopen(HF_URL, timeout=60) as stream:
        for raw in stream:
            line = raw.decode("utf-8").strip()
            match = re.match(r"^(\d+)\s*=\s*(.*)$", line)
            if not match:
                continue
            n = int(match.group(1))
            if n > limit:
                break
            if n == 0:
                continue
            xs = tuple(int(x) for x in re.findall(r"\((-?\d+)\)\^3", match.group(2)))
            yield n, xs


def infer_d(n, xs):
    x1, x2, x3, x4 = xs
    return x3 + x4 if n % 9 == 4 else -x3 - x4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--solver-limit", type=int, default=10000)
    parser.add_argument("--progress", type=int, default=1000)
    parser.add_argument("--show", type=int, default=40)
    args = parser.parse_args()

    ref = load_reference_module()
    start = time.monotonic()
    exact = same_d = d_diff = 0
    hf_invalid = script_invalid = script_missing = 0
    height_larger = height_smaller = height_equal = 0
    shown_same_d = shown_d_diff = 0

    for n, hxs in parse_hf_rows(args.limit):
        if not ref.verify(n, hxs):
            hf_invalid += 1
            continue
        hd = int(infer_d(n, hxs))
        hh = ref.height(hxs)
        sol = ref.solve(n, limit=args.solver_limit, return_d=True)
        if sol is None:
            script_missing += 1
            continue
        sxs = tuple(sol[:4])
        sd = int(sol[4])
        if not ref.verify(n, sxs):
            script_invalid += 1
            continue
        sh = ref.height(sxs)

        if sxs == hxs:
            exact += 1
        elif sd == hd:
            same_d += 1
            if shown_same_d < args.show:
                print(
                    f"SAME_D_TUPLE_DIFF n={n} d={hd} "
                    f"H_hf={hh} H_script={sh} hf={hxs} script={sxs}"
                )
                shown_same_d += 1
        else:
            d_diff += 1
            if shown_d_diff < args.show:
                print(
                    f"D_DIFF n={n} hf_d={hd} script_d={sd} "
                    f"H_hf={hh} H_script={sh} hf={hxs} script={sxs}"
                )
                shown_d_diff += 1

        if sh > hh:
            height_larger += 1
        elif sh < hh:
            height_smaller += 1
        else:
            height_equal += 1

        if args.progress and n % args.progress == 0:
            elapsed = time.monotonic() - start
            rate = n / elapsed if elapsed else 0.0
            print(
                f"PROGRESS n={n} elapsed={elapsed:.2f}s rate={rate:.2f}/s "
                f"exact={exact} same_d={same_d} d_diff={d_diff}",
                flush=True,
            )

    elapsed = time.monotonic() - start
    processed = exact + same_d + d_diff + hf_invalid + script_invalid + script_missing
    print("SUMMARY")
    print(f"limit {args.limit}")
    print(f"processed {processed}")
    print(f"hf_invalid {hf_invalid}")
    print(f"script_missing {script_missing}")
    print(f"script_invalid {script_invalid}")
    print(f"exact_tuple_match {exact}")
    print(f"tuple_mismatch_same_d {same_d}")
    print(f"d_mismatch {d_diff}")
    print(f"height_larger {height_larger}")
    print(f"height_smaller {height_smaller}")
    print(f"height_equal {height_equal}")
    print(f"elapsed_seconds {elapsed:.6f}")
    print(f"rate_per_second {processed / elapsed if elapsed else 0.0:.6f}")


if __name__ == "__main__":
    main()
