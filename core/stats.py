# language: Python 3, file: core/stats.py
import sys, threading, time

class Stats:
    def __init__(self):
        self._lock = threading.Lock()
        self.pkts = 0
        self.bytes = 0
        self.ok = 0
        self.fail = 0
        self.errors = []
        self._stop = threading.Event()
        self._thread = None

    def reset(self):
        with self._lock:
            self.pkts = self.bytes = self.ok = self.fail = 0
            self.errors.clear()

    def bump(self, n, ok=True, err=None):
        with self._lock:
            self.pkts += 1
            self.bytes += n
            if ok:
                self.ok += 1
            else:
                self.fail += 1
                if err:
                    s = f"{type(err).__name__}: {err}"
                    if s not in self.errors:
                        self.errors.append(s)
                        if len(self.errors) > 8:
                            self.errors.pop(0)

    def snapshot(self):
        with self._lock:
            return {
                "pkts": self.pkts, "bytes": self.bytes,
                "ok": self.ok, "fail": self.fail,
                "errors": list(self.errors),
            }

    def start_print(self, cy, r, dt=1.0):
        self._stop.clear()
        def loop():
            last_s = last_b = 0
            last_t = time.time()
            while not self._stop.is_set():
                time.sleep(dt)
                now = time.time()
                snap = self.snapshot()
                pps = snap["pkts"] - last_s
                bps = (snap["bytes"] - last_b) * 8 / max(now - last_t, 0.001)
                tot = snap["ok"] + snap["fail"]
                rasio = (snap["ok"] / max(tot, 1)) * 100
                sys.stdout.write(
                    f"\r{cy}  {pps:>6} pkt/s  {bps/1e6:>6.2f} Mbps  "
                    f"total {snap['pkts']:>9}  ok {snap['ok']}  fail {snap['fail']}  "
                    f"rasio {rasio:>5.1f}%{r}"
                )
                sys.stdout.flush()
                last_s, last_b, last_t = snap["pkts"], snap["bytes"], now
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop_print(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        print()