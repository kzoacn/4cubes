"""Reference Sage/Python implementation for the four-cubes Pell search.

Run with:
    sage -python scripts/four_cubes_reference.py

or pass targets explicitly:
    sage -python scripts/four_cubes_reference.py 254 314159265358979323
"""

import sys

from sage.all import ZZ, BinaryQF, Mod, factor, is_square


def passes_local_tests(n, d, M):
    """Return whether the necessary square tests used in the search pass."""
    for p, a in factor(d):
        q = p**a
        if not Mod(M, q).is_square():
            return False
    return True


def solve_pell_with_parity(d, M):
    """Find Pell candidates satisfying the required parity conditions."""
    Q = BinaryQF([1, 0, -d])
    for u, v in Q.solve_integer(M, _flag=3):
        u, v = ZZ(u), ZZ(v)
        if (u - 1) % 2 == 0 and (v - d) % 2 == 0:
            yield u, v


def quadruple_from_pell(d, u, v):
    """Convert a parity-compatible Pell solution to a four-cube tuple."""
    x = (u - 1) // 2
    y = (v - d) // 2
    return (x + 1, -x, -(y + d), y)


def height(xs):
    """Return H=max_i |x_i|."""
    return max(abs(x) for x in xs)


def solve(n, limit=10**8, return_d=False):
    """Return one quadruple whose cubes sum to n, or None."""
    n = ZZ(n)
    if n % 9 == 4:
        sol = solve(-n, limit=limit, return_d=True)
        if sol is None:
            return None
        x1, x2, x3, x4, d = sol
        out = (-x1, -x2, -x3, -x4)
        return out + (d,) if return_d else out

    residue = ZZ((1 - n) % 6)
    if residue == 0:
        residue = ZZ(6)

    for d in range(residue, limit + 1, 6):
        d = ZZ(d)
        if is_square(d):
            continue

        numerator = 4*n - 1 + d**3
        if numerator % 3 != 0:
            continue
        M = numerator // 3

        if not passes_local_tests(n, d, M):
            continue

        candidates = [
            quadruple_from_pell(d, u, v)
            for u, v in solve_pell_with_parity(d, M)
        ]
        if not candidates:
            continue

        out = min(
            candidates,
            key=lambda xs: (height(xs), tuple(xs)),
        )
        return out + (d,) if return_d else out

    return None


def verify(n, xs):
    """Check x1^3 + x2^3 + x3^3 + x4^3 = n exactly."""
    return sum(ZZ(x)**3 for x in xs) == ZZ(n)


def main(argv):
    targets = [ZZ(arg) for arg in argv]
    if not targets:
        targets = [
            ZZ(254),
            ZZ(314159265358979323),
            ZZ(27182818284590452),
        ]

    for n in targets:
        sol = solve(n, limit=2000, return_d=True)
        ok = sol is not None and verify(n, sol[:4])
        print(f"n = {n}")
        print(f"solution = {sol}")
        print(f"verified = {ok}")
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
