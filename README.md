---
license: cc-by-4.0
task_categories:
- tabular-regression
language:
- en
pretty_name: Sum of Four Cubes Certificates
---

# Sum of Four Cubes Certificates

This dataset contains explicit certificates for

```text
n = x1^3 + x2^3 + x3^3 + x4^3
```

for every integer `0 <= n <= 1,000,000,000`.

Each row has the form

```text
123 = (x1)^3 + (x2)^3 + (x3)^3 + (x4)^3
```

The files are sharded by intervals of length `10,000,000`, with the endpoint
`1,000,000,000` appended to the last shard:

```text
cubes-00.txt   0 <= n <= 9,999,999
cubes-01.txt   10,000,000 <= n <= 19,999,999
...
cubes-99.txt   990,000,000 <= n <= 1,000,000,000
```

The generation code uses a congruence-filtered generalized Pell search.  For
the first successful search parameter `d`, it records the representation with
minimal height

```text
H = max(|x1|, |x2|, |x3|, |x4|)
```

among the parity-compatible Pell representatives returned by the reference
solver.

## Reproduce

Generate shards with 15 worker processes:

```bash
sage -python scripts/generate_hf_dataset.py \
  --start 0 --end 1000000000 \
  --workers 15 \
  --chunk-size 10000 \
  --max-in-flight 30 \
  --out-dir generated/sum4cubes \
  --overwrite \
  --merge-final-singleton \
  --progress-every 10000000
```

For long runs, restart the generator from shard boundaries with `--resume`.
For example:

```bash
sage -python scripts/generate_hf_dataset.py \
  --start 80000000 --end 129999999 \
  --workers 15 \
  --chunk-size 10000 \
  --max-in-flight 30 \
  --out-dir generated/sum4cubes \
  --resume
```

Run a lightweight post-generation sanity check:

```bash
python3 scripts/check_generated_shards.py \
  --dir generated/sum4cubes \
  --start 0 --end 1000000000
```

The generator verifies each identity using exact integer arithmetic before
writing a row.  The sanity checker verifies shard coverage and exact
four-cube identities for boundary rows.
