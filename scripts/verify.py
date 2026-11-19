#!/usr/bin/env python3
"""End-to-end regression tests using the built executable and MPI launcher."""
import argparse
import json
import os
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--binary', default='build/heat')
p.add_argument('--mpirun', default='mpirun')
a = p.parse_args()
env = os.environ.copy()
env.update(OMP_PROC_BIND='close', OMP_PLACES='cores')

def run(ranks, mode, n, steps, threads=1, init='hotspots', extra=()):
    cmd = [a.mpirun, '-np', str(ranks), a.binary, '--mode', mode, '--size', str(n),
           '--steps', str(steps), '--threads', str(threads), '--init', init,
           '--verify', *extra]
    result = subprocess.run(cmd, check=True, text=True, capture_output=True, env=env)
    data = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
    assert data['verified'] and data['verify_error'] <= 1e-10, (cmd, data)
    print(f"PASS {mode:15} {n:4} {ranks}x{threads} {init:8} error={data['verify_error']:.2e}")
    return data

for mode in ('seq_naive', 'seq_tiled', 'omp', 'mpi', 'hybrid', 'hybrid_overlap'):
    ranks = 3 if mode in ('mpi', 'hybrid', 'hybrid_overlap') else 1
    threads = 2 if mode in ('omp', 'hybrid', 'hybrid_overlap') else 1
    run(ranks, mode, 128, 20, threads)
    run(ranks, mode, 131, 13, threads, 'random', ('--local-init',))
for ranks, threads in ((1, 4), (2, 2), (4, 1)):
    run(ranks, 'hybrid_overlap', 129, 15, threads)
run(2, 'hybrid_overlap', 1024, 3, 2)
analytic = run(3, 'hybrid_overlap', 127, 25, 2, 'sine')
assert analytic['analytic_error'] < 1e-10, analytic
print('All numerical regression and analytic sine mode checks passed.')
