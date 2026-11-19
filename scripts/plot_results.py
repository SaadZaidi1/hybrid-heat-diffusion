#!/usr/bin/env python3
"""Regenerate plots exclusively from measured benchmark CSV rows."""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument('csv', nargs='*', default=['results/benchmarks.csv'])
a = p.parse_args()
df = pd.concat([pd.read_csv(path) for path in a.csv], ignore_index=True)
out = Path('results/plots')
out.mkdir(parents=True, exist_ok=True)
if df.empty:
    raise SystemExit('No measured rows in CSV')
df['cores'] = df.ranks * df.threads
d = df.groupby(['size', 'mode', 'ranks', 'threads', 'tile', 'cores'], as_index=False)[['total_s', 'compute_s', 'comm_s']].median()
for n, group in d.groupby('size'):
    baseline = float(group[group['mode'] == 'seq_tiled']['total_s'].min())
    group = group.copy()
    group['speedup'] = baseline / group.total_s
    group['efficiency'] = group.speedup / group.cores
    plotted = pd.concat([
        group[(group['mode'] != 'seq_tiled') & (group['tile'] == 64)],
        group[group['mode'] == 'seq_tiled'].sort_values('total_s').drop_duplicates('cores')
    ])
    for metric, ylabel in [('total_s', 'Time (s)'), ('speedup', 'Speedup'), ('efficiency', 'Efficiency')]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for mode, g in plotted.groupby('mode'):
            best = g.groupby('cores', as_index=False)[metric].min() if metric == 'total_s' else g.groupby('cores', as_index=False)[metric].max()
            ax.plot(best.cores, best[metric], 'o-', label=mode)
        if metric == 'speedup':
            ax.plot(sorted(group.cores.unique()), sorted(group.cores.unique()), 'k--', label='ideal')
        ax.set(xlabel='Total cores', ylabel=ylabel, title=f'{n} × {n} grid')
        ax.legend(fontsize=7); ax.grid(alpha=.3); fig.tight_layout()
        fig.savefig(out / f'{n}_{metric}.png', dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for (mode, ranks, threads), g in group[group.cores > 1].groupby(['mode', 'ranks', 'threads']):
        if mode in ('mpi', 'omp', 'hybrid', 'hybrid_overlap'):
            ax.scatter(g.cores, g.total_s, label=f'{mode} {ranks}×{threads}')
    ax.set(xlabel='Total cores', ylabel='Time (s)', title=f'{n} × {n}: process/thread splits')
    ax.legend(fontsize=6, ncol=2); fig.tight_layout(); fig.savefig(out / f'{n}_splits.png', dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for mode in ('hybrid', 'hybrid_overlap'):
        g = group[group['mode'] == mode].groupby('cores', as_index=False)['total_s'].min()
        ax.plot(g.cores, g.total_s, 'o-', label=mode)
    ax.set(xlabel='Total cores', ylabel='Time (s)', title=f'{n} × {n}: overlap')
    ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(out / f'{n}_overlap.png', dpi=150); plt.close(fig)
    b = group[group['tile'] == 64].sort_values('cores')
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [f'{r.mode}\n{r.ranks}×{r.threads}' for r in b.itertuples()]
    x = range(len(b))
    ax.bar(x, b.compute_s, label='compute'); ax.bar(x, b.comm_s, bottom=b.compute_s, label='communication')
    ax.set_xticks(list(x), labels, rotation=70, fontsize=6)
    ax.set(ylabel='Time (s)', title=f'{n} × {n}: measured components')
    ax.legend(); fig.tight_layout(); fig.savefig(out / f'{n}_breakdown.png', dpi=150); plt.close(fig)
    g = group[group['mode'] == 'seq_tiled'].sort_values('tile')
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(g.tile, g.total_s, 'o-'); ax.set(xlabel='Tile size', ylabel='Time (s)', title=f'{n} × {n}: tile sweep')
    ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(out / f'{n}_tiles.png', dpi=150); plt.close(fig)
print('Saved plots to', out)
