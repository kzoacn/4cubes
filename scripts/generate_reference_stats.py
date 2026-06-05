"""Generate tables and figure data for the reference four-cubes solver.

Run with:
    sage -python scripts/generate_reference_stats.py --limit 10000000
"""

import argparse
import importlib.util
import math
import time
from pathlib import Path


BIN_WIDTH = 10000
SAMPLE_STEP = 5000
AVG_STEP = 10000
TOPK = 20


def load_reference_module():
    spec = importlib.util.spec_from_file_location(
        "four_cubes_reference", "scripts/four_cubes_reference.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def theory_x(n):
    ln = math.log(n)
    return math.sqrt(ln * math.log(ln))


def log10_int(x):
    s = str(abs(int(x)))
    take = min(len(s), 16)
    return len(s) - take + math.log10(float(s[:take]))


def cube_term(x):
    x = int(x)
    return f"({x})^3" if x < 0 else f"{x}^3"


def tex_row(n, xs, d):
    return (
        f"{n} & ${cube_term(xs[0])} + {cube_term(xs[1])} + "
        f"{cube_term(xs[2])} + {cube_term(xs[3])}$ & {d} \\\\"
    )


def maybe_insert_top(top, item, key):
    top.append(item)
    top.sort(key=key, reverse=True)
    del top[TOPK:]


def quantile(sorted_values, q):
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int(q * (len(sorted_values) - 1))
    return sorted_values[idx]


def flush_bin(f, current_bin, values, limit):
    if current_bin < 0 or not values:
        return
    values.sort()
    lo = current_bin * BIN_WIDTH + 1
    hi = min(lo + BIN_WIDTH - 1, limit)
    mid = (lo + hi) // 2
    mean = sum(values) / len(values)
    f.write(
        f"{mid} {mean:.8f} {quantile(values, 0.50)} "
        f"{quantile(values, 0.90)} {quantile(values, 0.99)} "
        f"{quantile(values, 0.999)} {values[-1]}\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10_000_000)
    parser.add_argument("--solver-limit", type=int, default=1_000_000)
    parser.add_argument("--outdir", default="figures/data")
    parser.add_argument("--analysis-dir", default="analysis")
    parser.add_argument("--progress", type=int, default=100_000)
    args = parser.parse_args()

    ref = load_reference_module()
    outdir = Path(args.outdir)
    analysis_dir = Path(args.analysis_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    sample = (outdir / "d_sample.dat").open("w")
    quantiles = (outdir / "d_quantiles.dat").open("w")
    average = (outdir / "d_average.dat").open("w")
    outliers = (outdir / "d_outliers.dat").open("w")
    fit_params = (outdir / "d_fit_params.dat").open("w")
    first100 = (analysis_dir / "reference_1e7_first100.tex").open("w")
    top_tsv = (analysis_dir / "reference_1e7_top.tsv").open("w")

    sample.write("n d\n")
    quantiles.write("n mean median p90 p99 p999 max\n")
    average.write("n avg model\n")
    outliers.write("n d\n")

    cumulative = 0.0
    avg_points = []
    fit_x = []
    fit_y = []
    bin_values = []
    current_bin = -1
    top_d = []
    top_h = []
    top_d_over_n = []
    top_h_over_n = []

    start = time.monotonic()
    for n in range(1, args.limit + 1):
        sol = ref.solve(n, limit=args.solver_limit, return_d=True)
        if sol is None:
            raise RuntimeError(f"no solution found for n={n}")
        xs = tuple(sol[:4])
        d = int(sol[4])
        if not ref.verify(n, xs):
            raise RuntimeError(f"invalid identity for n={n}: {xs}")
        h = int(ref.height(xs))

        if n <= 100:
            first100.write(tex_row(n, xs, d) + "\n")

        bin_id = (n - 1) // BIN_WIDTH
        if bin_id != current_bin:
            flush_bin(quantiles, current_bin, bin_values, args.limit)
            bin_values = []
            current_bin = bin_id
        bin_values.append(d)

        cumulative += d
        if n % SAMPLE_STEP == 0:
            sample.write(f"{n} {d}\n")
        if n % AVG_STEP == 0:
            avg = cumulative / n
            x = theory_x(n)
            fit_x.append(x)
            fit_y.append(avg)
            avg_points.append((n, avg, x))

        log_h_over_n = log10_int(h) - math.log10(n if n > 1 else 2)
        record = {
            "n": n,
            "d": d,
            "h": h,
            "digits_h": len(str(h)),
            "log_h_over_n": log_h_over_n,
            "xs": xs,
        }
        maybe_insert_top(top_d, record, lambda r: (r["d"], -r["n"]))
        maybe_insert_top(top_h, record, lambda r: (r["h"], -r["n"]))
        maybe_insert_top(top_d_over_n, record, lambda r: (r["d"] / r["n"], -r["n"]))
        maybe_insert_top(top_h_over_n, record, lambda r: (r["log_h_over_n"], -r["n"]))

        if args.progress and n % args.progress == 0:
            elapsed = time.monotonic() - start
            print(
                f"PROGRESS n={n} elapsed={elapsed:.2f}s "
                f"rate={n / elapsed:.2f}/s",
                flush=True,
            )

    flush_bin(quantiles, current_bin, bin_values, args.limit)

    count = len(fit_x)
    sx = sum(fit_x)
    sy = sum(fit_y)
    sxx = sum(x * x for x in fit_x)
    sxy = sum(x * y for x, y in zip(fit_x, fit_y))
    denom = count * sxx - sx * sx
    slope = (count * sxy - sx * sy) / denom if denom else 0.0
    intercept = (sy - slope * sx) / count if count else 0.0
    fit_params.write("slope intercept\n")
    fit_params.write(f"{slope:.12f} {intercept:.12f}\n")
    for n, avg, x in avg_points:
        average.write(f"{n} {avg:.12f} {intercept + slope * x:.12f}\n")

    for item in top_d[:10]:
        outliers.write(f"{item['n']} {item['d']}\n")

    def write_top(name, rows):
        top_tsv.write(f"# {name}\n")
        top_tsv.write("rank\tn\td\tH\tH_digits\tlog10_H_over_n\txs\n")
        for rank, item in enumerate(rows[:20], 1):
            xs = ",".join(str(x) for x in item["xs"])
            top_tsv.write(
                f"{rank}\t{item['n']}\t{item['d']}\t{item['h']}\t"
                f"{item['digits_h']}\t{item['log_h_over_n']:.12f}\t{xs}\n"
            )

    write_top("largest_d", top_d)
    write_top("largest_H", top_h)
    write_top("largest_d_over_n", top_d_over_n)
    write_top("largest_log10_H_over_n", top_h_over_n)

    for f in [sample, quantiles, average, outliers, fit_params, first100, top_tsv]:
        f.close()

    elapsed = time.monotonic() - start
    print(f"SUMMARY limit={args.limit} elapsed={elapsed:.6f} rate={args.limit / elapsed:.6f}/s")
    print(f"largest_d n={top_d[0]['n']} d={top_d[0]['d']}")
    print(f"largest_H n={top_h[0]['n']} H={top_h[0]['h']}")
    print(f"slope={slope:.12f} intercept={intercept:.12f}")


if __name__ == "__main__":
    main()
