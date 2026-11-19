#!/usr/bin/env python3
"""Repeatable benchmark runner. Only measured runs are written to CSV."""
import argparse
import csv
import json
import os
import pathlib
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--binary', default='build/heat')
p.add_argument('--mpirun', default='mpirun')
p.add_argument('--quick', action='store_true')
p.add_argument('--repeats', type=int, default=5)
p.add_argument('--steps', type=int)
p.add_argument('--sizes', type=int, nargs='*')
p.add_argument('--output', default='results/benchmarks.csv')
a = p.parse_args()
cores = os.cpu_count() or 1
sizes = a.sizes or ([128, 256] if a.quick else [2048, 4096, 8192])
steps = a.steps if a.steps is not None else (10 if a.quick else 1000)
splits = [c for c in (1, 2, 4, 8, 16) if c <= cores]
tiles = (32, 64) if a.quick else (32, 64, 128, 256)
env = os.environ.copy()
env.update(OMP_PROC_BIND='close', OMP_PLACES='cores')
path = pathlib.Path(a.output)
path.parent.mkdir(parents=True, exist_ok=True)
fields = ['timestamp_utc', 'mode', 'size', 'steps', 'ranks', 'threads', 'tile', 'repeat',
          'init_s', 'comm_s', 'compute_s', 'total_s', 'gflops', 'updates_per_s',
          'sum', 'mean', 'min', 'max', 'center', 'verify_error', 'analytic_error']

def measure(n, mode, ranks, threads, tile):
    command = [a.mpirun, '-np', str(ranks), a.binary, '--size', str(n), '--steps', str(steps),
               '--mode', mode, '--threads', str(threads), '--tile', str(tile)]
    for rep in range(-1, a.repeats):
        result = subprocess.run(command, text=True, capture_output=True, env=env)
        if result.returncode:
            print('SKIP', command, result.stderr[-500:])
            return
        data = json.loads(next(x for x in result.stdout.splitlines() if x.startswith('{')))
        if rep >= 0:
            yield {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   **{k: data.get(k) for k in fields if k in data}, 'repeat': rep}

with path.open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    for n in sizes:
        configs = [('seq_tiled', 1, 1, t) for t in tiles]
        if n == min(sizes):
            configs.append(('seq_naive', 1, 1, 64))
        for c in splits:
            configs.append(('omp', 1, c, 64))
            configs.append(('mpi', c, 1, 64))
            for ranks in (r for r in (1, 2, 4, 8, 16) if r <= c and c % r == 0):
                if ranks == 1 and c == 1:
                    continue
                for mode in ('hybrid', 'hybrid_overlap'):
                    configs.append((mode, ranks, c // ranks, 64))
        for mode, ranks, threads, tile in dict.fromkeys(configs):
            print(f'{n} {mode} {ranks}x{threads} tile={tile}', flush=True)
            for row in measure(n, mode, ranks, threads, tile):
                writer.writerow(row)
                handle.flush()
print('Saved', path)
