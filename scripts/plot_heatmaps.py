#!/usr/bin/env python3
"""Run a small grid at selected times and plot the resulting temperature fields."""
import argparse
import csv
from pathlib import Path
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--binary', default='build/heat')
p.add_argument('--size', type=int, default=128)
a = p.parse_args()
out = Path('results/plots')
out.mkdir(parents=True, exist_ok=True)
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
for ax, steps in zip(axes, (0, 50, 200)):
    dump = out / f'field_{steps}.csv'
    subprocess.run([a.binary, '--mode', 'seq_tiled', '--size', str(a.size),
                    '--steps', str(steps), '--dump', str(dump)], check=True, capture_output=True)
    grid = np.zeros((a.size, a.size))
    with dump.open(newline='') as handle:
        for row in csv.DictReader(handle):
            grid[int(row['y']), int(row['x'])] = float(row['temperature'])
    image = ax.imshow(grid, vmin=0, vmax=100, cmap='inferno', origin='lower')
    ax.set_title(f'{steps} steps')
    dump.unlink()
fig.colorbar(image, ax=axes, label='Temperature')
fig.savefig(out / 'heatmaps.png', dpi=160)
print('Saved', out / 'heatmaps.png')
