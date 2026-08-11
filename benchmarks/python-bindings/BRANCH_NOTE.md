# ArcadeDB SciPy 2026 — experiments

This `arcadedb-2026` branch is the author's all-in-one branch for the SciPy 2026
ArcadeDB submission: the paper (`papers/taewoon_kim/`), the virtual poster
(`presentations/posters/taewoon_kim/`), and these benchmark experiments.
Only the paper is part of the upstream proceedings PR
(branch `paper-taewoon-kim`).

- `datasets/` raw/prepared payloads are not committed; `datasets/prepare.py`
  rebuilds them (see `README.md` for sources).
- `results/` and `figures/` are the runs used by the paper's tables/figures.
- Benchmarks run pinned inside Docker (`docker/`, `build_images.sh`); the
  ArcadeDB backend uses the `arcadedb-embedded` wheel (see Dockerfile ARG).
