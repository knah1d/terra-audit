"""Measure explanation stages without logging prompts, evidence or credentials."""
from contextlib import contextmanager
import logging
from time import perf_counter

log = logging.getLogger("ai.explanation.timing")


class StageTimings:
    def __init__(self, scope, job_id=None):
        self.scope = scope
        self.job_id = job_id
        self.seconds = {}
        self.started = perf_counter()

    @contextmanager
    def measure(self, stage):
        started = perf_counter()
        outcome = "ok"
        try:
            yield
        except BaseException:
            outcome = "error"
            raise
        finally:
            elapsed = perf_counter() - started
            self.seconds[stage] = round(self.seconds.get(stage, 0) + elapsed, 4)
            log.info("ai_explain scope=%s job=%s stage=%s seconds=%.4f outcome=%s",
                     self.scope, self.job_id or "none", stage, elapsed, outcome)

    def snapshot(self):
        return {**self.seconds, "total": round(perf_counter() - self.started, 4)}
