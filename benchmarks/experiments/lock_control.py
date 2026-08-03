#!/usr/bin/env python3
"""Positive control for asprof -e lock.

The #5577 silent-phase lock profile came back empty. Empty means "no contention"
ONLY if the event can produce output at all on this JVM and this binary. #5588
is the cautionary tale: three configurations of --live returned confident zeros
that meant the instrument could not see the thing, not that the thing was absent.

So: manufacture contention that must show up, profile it the same way, and see.
Six Java threads hammering one synchronized block. If this profile is also
empty, -e lock does not work here and the #5577 zero carries no information.
"""
import os, sys, time
import arcadedb_embedded as arcadedb   # brings up the JVM

def main():
    import jpype
    if not jpype.isJVMStarted():
        # a database start is the supported way to get the JVM up
        db = arcadedb.create_database(os.path.expanduser("~/.cache/lockctl_db"),
                                      jvm_kwargs={"heap_size": "2g"})
    print("JVM up; building contention", flush=True)

    # One lock, six threads, tight critical section: guaranteed monitor contention.
    Thread = jpype.JClass("java.lang.Thread")
    Runnable = jpype.JClass("java.lang.Runnable")
    src = """
    public class Contender implements Runnable {
      public static final Object LOCK = new Object();
      public static volatile boolean stop = false;
      public static long counter = 0;
      public void run() {
        while (!stop) {
          synchronized (LOCK) {
            for (int i = 0; i < 2000; i++) counter += i;
          }
        }
      }
    }
    """
    # Compiling Java at runtime is more machinery than this needs; use JPype's
    # thread wrapper over a Python callable instead, which still contends on a
    # Java monitor because the lock object is a Java object.
    lock = jpype.JClass("java.lang.Object")()
    sync = jpype.JClass("java.util.concurrent.locks.ReentrantLock")()
    stop = [False]

    @jpype.JImplements("java.lang.Runnable")
    class Worker:
        @jpype.JOverride
        def run(self):
            while not stop[0]:
                sync.lock()
                try:
                    x = 0
                    for i in range(2000):
                        x += i
                finally:
                    sync.unlock()

    threads = [Thread(Worker()) for _ in range(6)]
    for t in threads:
        t.start()
    print("6 threads contending on one ReentrantLock", flush=True)
    print(f"PID {os.getpid()}", flush=True)
    time.sleep(float(os.environ.get("HOLD_S", "120")))
    stop[0] = True
    for t in threads:
        t.join(2000)
    print("done", flush=True)

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback; traceback.print_exc(); sys.stdout.flush(); os._exit(1)
    sys.stdout.flush(); os._exit(0)
