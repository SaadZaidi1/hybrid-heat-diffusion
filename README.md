# Parallel 2D Heat Diffusion with Hybrid MPI and OpenMP

A C++17 implementation of explicit two-dimensional heat diffusion, comparing a naive sequential loop, a tiled sequential loop, OpenMP, MPI, and hybrid MPI/OpenMP with blocking and overlapped halo exchanges. Built for the Parallel and Distributed Computing course by Sajjad Ahmed (23K-0754), Wali Uddin (23K-0719), and Saad Zaidi (23K-0874).

## Numerical method

Each interior cell is updated with the five-point stencil

```text
u_new[y,x] = u[y,x] + alpha*dt/dx² *
             (u[y-1,x] + u[y+1,x] + u[y,x-1] + u[y,x+1] - 4*u[y,x])
```

Boundary cells stay fixed at `--boundary` (default zero). The default time step is `0.9 dx²/(4 alpha)`; larger values than `dx²/(4 alpha)` are rejected. Double-precision grids use two contiguous row-major arrays and pointer swaps. `hotspots` gives two fixed Gaussian hot spots; `random` uses a coordinate hash and `--seed` so each strip can regenerate the same values independently. `sine` supplies a discrete eigenmode with a known exact decay for testing.

## Parallel layout

```text
rank 0: [ fixed top | owned rows ... | halo from rank 1 ]
rank 1: [ halo from 0 | owned rows ... | halo from 2 ]
rank 2: [ halo from 1 | owned rows ... | fixed bottom ]
```

Ranks get contiguous horizontal strips; extra rows go to lower ranks. Rank 0 scatters a full input grid using `MPI_Scatterv`, then gathers the final field with `MPI_Gatherv`. `--local-init` generates strips from global coordinates to reduce initial root memory. Each process has top and bottom halo rows. `mpi` and `hybrid` use `MPI_Sendrecv` for halo exchange, followed by computation. `hybrid_overlap` posts four nonblocking requests, computes rows that do not depend on incoming halos, waits, then computes strip edge rows. MPI is initialized with `MPI_THREAD_FUNNELED`, and all MPI calls stay on the main thread. OpenMP uses static row or tile scheduling, SIMD inner loops, and first-touch array initialization. Set `OMP_PROC_BIND=close` and `OMP_PLACES=cores` for pinning; MPI launchers commonly support `--bind-to core` (check your launcher).

## Build

On Linux, install a C++17 compiler, CMake, Make, OpenMPI or MPICH development packages, Python 3, and `python3 -m pip install -r scripts/requirements.txt`. Then:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
# or: make
```

The default binary is `build/heat`. Compilation uses `-O3 -march=native -Wall -Wextra` with GNU/Clang. For portable binaries, remove `-march=native` from CMake options.

## Run

```bash
./build/heat --mode seq_naive --size 128 --steps 100
./build/heat --mode seq_tiled --size 2048 --steps 1000 --tile 64
./build/heat --mode omp --size 2048 --threads 8
mpirun -np 8 ./build/heat --mode mpi --threads 1
mpirun -np 4 ./build/heat --mode hybrid --threads 2
mpirun -np 2 ./build/heat --mode hybrid_overlap --threads 4
mpirun -np 4 ./build/heat --mode hybrid_overlap --threads 2 --init random --seed 17 --local-init --verify
./build/heat --size 128 --steps 50 --dump results/dumps/heat.csv
```

The JSON output reports rank-max initialization, communication (including final gather), computation, and wall time; GFLOPS counts five floating-point operations per interior update. It also reports sum, mean, extrema, center sample, and optional maximum relative verification error. `--output csv-line` prints a compact row without a header. Dumps are CSV, downsampled to at most roughly 256 points per axis. Use `--help` for all options. The solver rejects arrays with more than 2³¹−1 global elements due to the MPI `int` counts/displacements API; very large grids may also exceed available RAM.

## Tests and measurement

```bash
ctest --test-dir build --output-on-failure
python3 scripts/verify.py --binary build/heat
# or: make test
python3 scripts/benchmark.py --binary build/heat --quick --repeats 2
python3 scripts/benchmark.py --binary build/heat --repeats 5
python3 scripts/plot_results.py results/benchmarks.csv
```

`verify.py` compares every version against an independent sequential reference to relative tolerance `1e-10`, including uneven strips and a 1024² case, and checks the exact discrete sine-mode decay. The benchmark runner detects logical CPU count, runs a warmup before each configuration, sweeps core splits and tile sizes, and writes only measured results to `results/benchmarks.csv`. The full sweep includes 2048², 4096², and 8192², while `--quick` uses 128² and 256². The naive version runs only on the smallest grid. The plotting script reads the measured CSV and creates time, speedup, efficiency, split, overlap, breakdown, and tile plots in `results/plots/`.

## Results and limits

Measurement results and this machine's specifications will be added after the local toolchain is available and benchmark runs complete. Do not treat unmeasured configurations as results. Expected limits to examine are communication per strip, cache behavior and memory bandwidth, unequal strip sizes, and MPI/OpenMP startup and scheduling overhead. On large grids, compare speedup against the single-thread tiled implementation.

## Files

- `src/main.cpp`: CLI, initialization, kernels, MPI decomposition and halo logic, verification, metrics.
- `scripts/verify.py`: numerical regression and analytic test.
- `scripts/benchmark.py`: warmup, repeated measurements and sweep.
- `scripts/plot_results.py`: graphs generated from CSV.
- `results/`: measured CSV and plots.

MIT licensed; see [LICENSE](LICENSE).
