#!/usr/bin/env python3
"""One-time host-side prep: ann-benchmarks HDF5 -> raw .npy files so bench
containers need only numpy. Writes train/test/neighbors under data/dense/.
Usage: uv run --no-project --with h5py --with numpy python gen_dense_npy.py"""
import os
import h5py
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "dense")
f = h5py.File(os.path.join(D, "sift-128-euclidean.hdf5"), "r")
np.save(os.path.join(D, "sift_train.npy"), np.asarray(f["train"], dtype=np.float32))
np.save(os.path.join(D, "sift_test.npy"), np.asarray(f["test"], dtype=np.float32))
np.save(os.path.join(D, "sift_neighbors.npy"), np.asarray(f["neighbors"], dtype=np.int64))
print("train", f["train"].shape, "test", f["test"].shape, "gt", f["neighbors"].shape)
