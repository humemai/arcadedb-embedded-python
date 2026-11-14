"""Redis has a display name, so one engine reads as one version string on every table (2026-11-14, first landing of the n=3 rows).

`redis_tpc` had no entry in DISPLAY_NAMES, so its label was the key with the underscore made a space ('redis tpc'). The document tables name
the engine from its image ('redis 8.10.2') and the durability table from the label ('redis tpc 8.10.2'): version_consistency_check refused 'redis tpc
publishes 2 different version strings'. With a display name both read 'redis 8.10.2'.
Light: no files. Run with pytest, or as plain functions from this directory.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("BENCH_RESULTS_DIR", tempfile.mkdtemp(prefix="display-names-"))
os.environ.setdefault("BENCH_ONLY_LANES", "l1tpc")
import export_web as EW  # noqa: E402


def test_the_label_and_the_image_give_one_version_string():
    for key, name, raw, image in (("redis_tpc", "Redis", "redis:8.10.2", "redis@sha256:13ad"),):
        assert EW.display_name(key) == name, EW.display_name(key)
        from_label = EW._engine_version(EW.display_name(key), raw)
        from_image = EW._engine_version(EW.display_name(key), raw, image=image)
        assert from_label == from_image, (from_label, from_image)


if __name__ == "__main__":
    test_the_label_and_the_image_give_one_version_string()
    print("ok")
