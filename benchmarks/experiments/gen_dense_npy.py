#!/usr/bin/env python3
"""One-time host-side prep: ann-benchmarks HDF5 -> raw .npy files so bench
containers need only numpy.

Arrays are dumped AS SHIPPED. deep-image is an angular dataset, but the
unit-normalization l3d_dense.load_dataset() relies on happens there, at load
time, in a chunked pass sized against the client's memory share -- normalizing
here would apply it twice and silently change what the GT means.

The two corpora disagree on output names (sift_train vs deep_base) because the
DEEP files were produced by hand in July 2026, before this script covered them,
and l3d_dense loads them by those names. Renaming is not worth invalidating the
corpus already staged on the bench host.

Usage:
  # download once, into data/<subdir>/
  curl -LO http://ann-benchmarks.com/sift-128-euclidean.hdf5
  curl -LO http://ann-benchmarks.com/deep-image-96-angular.hdf5

  uv run --no-project --with h5py --with numpy python gen_dense_npy.py sift
  uv run --no-project --with h5py --with numpy python gen_dense_npy.py deep
"""
import os
import sys

import h5py
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# corpus -> (hdf5 basename, directory under data/, {hdf5 key: output suffix})
CORPORA = {
    "sift": ("sift-128-euclidean.hdf5", "dense",
             {"train": "sift_train", "test": "sift_test",
              "neighbors": "sift_neighbors"}),
    "deep": ("deep-image-96-angular.hdf5", "deep10m",
             {"train": "deep_base", "test": "deep_query",
              "neighbors": "deep_gt"}),
}
DTYPE = {"train": np.float32, "test": np.float32, "neighbors": np.int64}


def main(name):
    if name not in CORPORA:
        sys.exit(f"unknown corpus {name!r}; expected one of {'/'.join(CORPORA)}")
    h5, subdir, outputs = CORPORA[name]
    d = os.path.join(HERE, "data", subdir)
    src = os.path.join(d, h5)
    if not os.path.exists(src):
        sys.exit(f"{src} not found; download it first:\n"
                 f"  curl -L -o {src} http://ann-benchmarks.com/{h5}")
    with h5py.File(src, "r") as f:
        for key, stem in outputs.items():
            a = np.asarray(f[key], dtype=DTYPE[key])
            np.save(os.path.join(d, stem + ".npy"), a)
            print(stem, a.shape, a.dtype)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sift")
