"""Evict a database's pages from the page cache, and prove they left.

Cold open -- the first open after a boot, with nothing cached -- was the one
lifecycle question `lifecycle-open-close.md` recorded as untestable, because the
obvious instrument is `echo 3 > /proc/sys/vm/drop_caches` and mini has no
passwordless sudo.

`posix_fadvise(POSIX_FADV_DONTNEED)` needs no privileges and is a BETTER
instrument than drop_caches for this question, not merely an available one:

  - It evicts exactly the files named, leaving the rest of the host warm, so the
    measurement is "this database is cold" rather than "the machine is cold".
    drop_caches would also evict the JVM's own mapped jars and the driver's
    Python bytecode, charging their re-read to the engine's open time.
  - It perturbs nothing else on a shared bench host, so a cold-open cell can run
    between other cells without cooling them.

The catch, and the reason `verify=True` is the default: DONTNEED silently
declines to drop DIRTY pages. Eviction is therefore not a thing to assume -- so
`mincore(2)` reports how many pages are actually resident, and `evict()` raises
if they did not go. A cold-open number measured on a database that was still
cached is indistinguishable from a fast open, which is exactly the failure this
module exists to make impossible.
"""
import ctypes
import ctypes.util
import os

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
# ctypes defaults to a 32-bit int return, which TRUNCATES the 64-bit pointer
# mmap hands back; mincore then fails with ENOMEM against an address that was
# never mapped, and the obvious reading of that errno ("the file is too big")
# is wrong. Declare the types.
_libc.mmap.restype = ctypes.c_void_p
_libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                       ctypes.c_int, ctypes.c_int, ctypes.c_long]
_libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
_libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                          ctypes.POINTER(ctypes.c_ubyte)]

_PROT_READ = 1
_MAP_SHARED = 1


def resident_pages(path):
    """(resident, total) pages of `path` currently in the page cache."""
    fd = os.open(path, os.O_RDONLY)
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            return 0, 0
        mm = _libc.mmap(None, size, _PROT_READ, _MAP_SHARED, fd, 0)
        if mm is None:
            raise OSError(ctypes.get_errno(), f"mmap {path}")
        try:
            npages = (size + os.sysconf("SC_PAGESIZE") - 1) // os.sysconf("SC_PAGESIZE")
            vec = (ctypes.c_ubyte * npages)()
            if _libc.mincore(ctypes.c_void_p(mm), size, vec) != 0:
                raise OSError(ctypes.get_errno(), f"mincore {path}")
            return sum(1 for b in vec if b & 1), npages
        finally:
            _libc.munmap(ctypes.c_void_p(mm), size)
    finally:
        os.close(fd)


def _files(root):
    if os.path.isfile(root):
        return [root]
    out = []
    for dirpath, _, names in os.walk(root):
        out.extend(os.path.join(dirpath, n) for n in names)
    return out


def evict(root, verify=True, tolerance_pages=0):
    """Drop `root` (a file or a directory tree) from the page cache.

    Returns {"files", "pages_before", "pages_after", "bytes"}. Raises RuntimeError
    when `verify` and more than `tolerance_pages` survive: an un-evicted database
    reports a warm open under a cold label, which is worse than no measurement.
    """
    paths = _files(root)
    # fsync first. DONTNEED declines to drop dirty pages, so an unsynced database
    # evicts partially and reports a cold open that is nothing of the kind.
    os.sync()

    before = after = total_bytes = 0
    for p in paths:
        try:
            r, _ = resident_pages(p)
        except OSError:
            continue
        before += r
        try:
            fd = os.open(p, os.O_RDONLY)
        except OSError:
            continue
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            total_bytes += os.fstat(fd).st_size
        finally:
            os.close(fd)
        try:
            r2, _ = resident_pages(p)
        except OSError:
            r2 = 0
        after += r2

    if verify and after > tolerance_pages:
        raise RuntimeError(
            f"{after} pages of {root} survived eviction (was {before}). "
            "POSIX_FADV_DONTNEED does not drop dirty pages; something is still "
            "writing, or a process holds the file mapped. Refusing to report a "
            "cold measurement on a warm database.")
    return {"files": len(paths), "pages_before": before,
            "pages_after": after, "bytes": total_bytes}
