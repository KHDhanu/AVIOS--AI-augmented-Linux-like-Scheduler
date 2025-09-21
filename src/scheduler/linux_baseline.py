# ------------------------------
# LinuxBaselineScheduler
# ------------------------------
import heapq
import itertools
from collections import deque, defaultdict
import pandas as pd
import numpy as np
import time

class LinuxBaselineScheduler:
    """
    A lightweight Linux-like baseline scheduler simulator.
    - FIFO: first-in-first-out, runs until completion
    - RR: round-robin with fixed quantum
    - CFS: fair scheduling via vruntime min-heap
    - IDLE: runs when nothing else is available
    """

    def __init__(self, num_cores=4, core_priority_order=None,
                 rr_quantum=100, cfs_base_slice=4, seed=42):
        self.num_cores = num_cores
        self.rr_quantum = int(rr_quantum)
        self.cfs_base_slice = float(cfs_base_slice)  # used as base multiplier
        self.insertion_counter = itertools.count()
        self.seed = seed

        # per-core priority order (which scheduler to prefer on each core)
        self.core_priority_order = core_priority_order or {
            cid: ["FIFO", "RR", "CFS", "IDLE"] for cid in range(num_cores)
        }

        # queues: same shape as AIScheduler for easy comparison
        self.queues = {
            "FIFO": {"fifo_1": deque()},
            "RR": {"rr_1": deque()},
            "CFS": {"cfs_1": []},   # min-heaps of (vruntime, counter, pid, task)
            "IDLE": {"idle": deque()}
        }

        # cores state: dict per core: {"task": Task or None, "time_left": int quantum remaining}
        self.cores = {cid: {"task": None, "time_left": 0} for cid in range(num_cores)}

        # runtime bookkeeping
        self.time = 0
        self.logs = []            # list of event dicts
        self.task_map = {}        # pid -> Task
        self.completed_tasks = {}
        self.context_switches = 0

        # small constants to approximate Linux behavior
        self.NICE0_WEIGHT = 1024.0  # used for vruntime update
        self.min_granularity = 1    # minimum quantum tick granularity (1 tick)

    # --------------------
    # Utilities / helpers
    # --------------------
    def _log(self, event_type, task=None, core=None, extra=None):
        row = {
            "time": self.time,
            "event": event_type,
            "core": core,
            "pid": getattr(task, "pid", None),
            "name": getattr(task, "name", None),
        }
        if task is not None:
            row.update({
                "assigned_scheduler": task.assigned_scheduler,
                "subqueue": task.subqueue,
                "remaining": task.remaining,
                "quantum": task.quantum,
                "vruntime": getattr(task, "vruntime", None),
                "subqueue_score": getattr(task, "subqueue_score", None),
            })
        if extra:
            row.update(extra)
        self.logs.append(row)

    def all_queues_empty(self):
        # check both queue structures and running cores
        for sched in self.queues:
            for subq in self.queues[sched]:
                if len(self.queues[sched][subq]) > 0:
                    return False
        for cid in self.cores:
            if self.cores[cid]["task"] is not None:
                return False
        return True

    # --------------------
    # Enqueue / Dequeue
    # --------------------
    def _cfs_insert(self, subq, task):
        # push (vruntime, counter, pid, task)
        entry = (float(task.vruntime), next(self.insertion_counter), task.pid, task)
        heapq.heappush(self.queues["CFS"][subq], entry)

    def _cfs_pop_min(self, subq):
        heap = self.queues["CFS"][subq]
        while heap:
            vr, _, pid, task = heapq.heappop(heap)
            # lazy validity: if task.vruntime changed, the popped entry might be stale.
            # But we accept small differences; if wildly different, reinsert with current vruntime.
            if abs(float(task.vruntime) - float(vr)) < 1e-6:
                return task
            else:
                # stale entry: push a fresh one and continue popping next
                entry = (float(task.vruntime), next(self.insertion_counter), task.pid, task)
                heapq.heappush(heap, entry)
                # continue popping - eventual correct entry will match
        return None

    def _enqueue_task(self, task):
        """Place task into the queue structure according to assigned_scheduler/subqueue."""
        sched = task.assigned_scheduler or "CFS"
        subq = task.subqueue or (list(self.queues[sched].keys())[0])
        if sched == "CFS":
            self._cfs_insert(subq, task)
        else:
            self.queues[sched][subq].append(task)
        self._log("ENQUEUE", task)

    def _dequeue_task(self, sched, subq):
        if sched == "CFS":
            return self._cfs_pop_min(subq)
        else:
            q = self.queues[sched][subq]
            return q.popleft() if q else None

    # --------------------
    # Admission
    # --------------------
    def admit(self, task, current_time=None):
        """Admit new task. Assign scheduler from Scheduling_Policy if present, else default CFS."""
        if current_time is None:
            current_time = self.time
        task.arrival_time = int(task.arrival_time) if hasattr(task, "arrival_time") else int(current_time)
        self.task_map[task.pid] = task

        # use explicit Scheduling_Policy if provided in features
        sched_pol = str(task.features.get("Scheduling_Policy", "")).upper()
        if sched_pol == "SCHED_FIFO":
            task.assigned_scheduler = "FIFO"
            task.subqueue = "fifo_1"
        elif sched_pol == "SCHED_RR":
            task.assigned_scheduler = "RR"
            task.subqueue = "rr_1"
        elif sched_pol == "SCHED_IDLE":
            task.assigned_scheduler = "IDLE"
            task.subqueue = "idle"
        else:
            # fallback to CFS
            task.assigned_scheduler = "CFS"
            task.subqueue = "cfs_1"

        # set remaining if not already set (use Total_Time_Ticks if present)
        if getattr(task, "remaining", None) is None or task.remaining == 0:
            # total_time ticks might be in features
            task.remaining = int(task.features.get("Total_Time_Ticks", task.total_time or 1))

        # ensure vruntime and weight
        task.vruntime = float(task.features.get("se.vruntime", getattr(task, "vruntime", 0.0) or 0.0))
        task.weight = float(task.features.get("se.load.weight", getattr(task, "weight", 1024.0) or 1024.0))

        # for RR, set initial quantum
        if task.assigned_scheduler == "RR":
            task.quantum = max(self.min_granularity, int(self.rr_quantum))
        else:
            task.quantum = None

        # final enqueue
        self._log("ADMIT", task)
        self._enqueue_task(task)

    # --------------------
    # Core pick & dispatch
    # --------------------
    def _pick_task_for_core(self, core_id):
        order = self.core_priority_order.get(core_id, ["FIFO", "RR", "CFS", "IDLE"])
        for sched in order:
            # within a scheduler prefer higher subqueue keys in order (fifo_1 before fifo_2)
            subqueues = list(self.queues[sched].keys())
            for subq in subqueues:
                if len(self.queues[sched][subq]) == 0:
                    continue
                # for CFS peek min
                if sched == "CFS":
                    candidate = None
                    heap = self.queues["CFS"][subq]
                    # peek valid entry
                    if heap:
                        vr, _, pid, task = heap[0]
                        candidate = task
                else:
                    candidate = self.queues[sched][subq][0]
                if candidate is not None:
                    # pick first available per scheduler priority
                    return sched, subq
        return None, None

    def _dispatch_to_core(self, core_id, sched, subq):
        task = self._dequeue_task(sched, subq)
        if task is None:
            return None
        # initialize quantum for CFS using base slice formula if not RR/FIFO
        if sched == "CFS":
            runnable_set_weight = sum(
                 [t.weight if t.weight > 0 else self.NICE0_WEIGHT
                 for subq in self.queues["CFS"].values()
                  for _, _, _, t in subq]   # iterate over heap entries
            )
            if runnable_set_weight <= 0:
                   runnable_set_weight = task.weight or self.NICE0_WEIGHT
            sched_latency_ticks = 48  # you can tune (Linux default ~48ms window)
            proportion = (task.weight or self.NICE0_WEIGHT) / runnable_set_weight
            base_slice = int(sched_latency_ticks * proportion)

            task.quantum = max(self.min_granularity, base_slice)
        elif sched == "FIFO":
            # FIFO runs until completion (set quantum = remaining)
            task.quantum = max(1, int(task.remaining))
        elif sched == "RR":
            # round robin fixed quantum
            task.quantum = max(self.min_granularity, int(self.rr_quantum))
        else:
            task.quantum = max(1, int(task.remaining))

        # set running on core
        self.cores[core_id]["task"] = task
        self.cores[core_id]["time_left"] = int(task.quantum)
        if task.first_start is None:
            task.first_start = self.time
        self.context_switches += 1
        self._log("DISPATCH", task, core=core_id)
        return task

    # --------------------
    # Per-tick execution
    # --------------------
    def _update_vruntime(self, task, delta=1):
        # vruntime += delta * (NICE0_WEIGHT / weight)
        if task.weight <= 0:
            task.weight = 1.0
        task.vruntime += float(delta) * (self.NICE0_WEIGHT / float(task.weight))

    def _run_one_tick_on_core(self, core_id):
        core = self.cores[core_id]
        task = core["task"]
        if task is None:
            # idle; nothing to do
            return
        # run one tick
        task.remaining = max(0, int(task.remaining) - 1)
        task.total_run = getattr(task, "total_run", 0) + 1
        core["time_left"] = max(0, core["time_left"] - 1)

        # update vruntime only for CFS tasks
        if task.assigned_scheduler == "CFS":
            self._update_vruntime(task, delta=1)

        # log run
        self._log("RUN", task, core=core_id)

        # completion?
        if task.remaining <= 0:
            task.completion_time = self.time
            self.completed_tasks[task.pid] = task
            self._log("COMPLETE", task, core=core_id)
            # clear core
            core["task"] = None
            core["time_left"] = 0
            return

        # quantum expired?
        if core["time_left"] <= 0:
            # for RR → requeue to RR subqueue (round robin)
            if task.assigned_scheduler == "RR":
                self._log("PREEMPT", task, core=core_id, extra={"reason": "quantum_expired"})
                # requeue at end of its RR subqueue
                self.queues["RR"][task.subqueue].append(task)
                core["task"] = None
                core["time_left"] = 0
            elif task.assigned_scheduler == "CFS":
                # update vruntime already updated per tick; re-insert to heap
                self._log("PREEMPT", task, core=core_id, extra={"reason": "cfs_quantum_expired"})
                self._cfs_insert(task.subqueue, task)
                core["task"] = None
                core["time_left"] = 0
            elif task.assigned_scheduler == "FIFO":
                # FIFO shouldn't preempt on quantum expiry (we set quantum=remaining). But if it happens, requeue front.
                self._log("PREEMPT", task, core=core_id, extra={"reason": "fifo_preempt"})
                self.queues["FIFO"][task.subqueue].appendleft(task)
                core["task"] = None
                core["time_left"] = 0
            else:
                # IDLE or others
                core["task"] = None
                core["time_left"] = 0

    # --------------------
    # Main tick (called every simulated second/tick)
    # --------------------
    def tick(self, current_time=None):
        if current_time is None:
            current_time = self.time
        self.time = int(current_time)

        # for each core: if no running task try to pick one; else run one tick
        for cid in range(self.num_cores):
            if self.cores[cid]["task"] is None:
                sched, subq = self._pick_task_for_core(cid)
                if sched is not None:
                    self._dispatch_to_core(cid, sched, subq)
            # run one tick on the core (if any)
            self._run_one_tick_on_core(cid)

    # --------------------
    # Metrics & export
    # --------------------
    def export_logs(self):
        return pd.DataFrame(self.logs)

    def export_task_metrics(self):
        # build per-task metrics from completed_tasks + task_map
        rows = []
        for pid, task in self.task_map.items():
            if pid in self.completed_tasks:
                t = self.completed_tasks[pid]
                arrival = getattr(t, "arrival_time", None)
                first = getattr(t, "first_start", None)
                comp = getattr(t, "completion_time", None)
                exec_time = getattr(t, "total_run", 0)
                waiting = (first - arrival) if (first is not None and arrival is not None) else None
                turnaround = (comp - arrival) if (comp is not None and arrival is not None) else None
                response = waiting
                stretch = turnaround / exec_time if exec_time > 0 and turnaround is not None else None
                rows.append({
                    "pid": pid, "name": t.name,
                    "arrival": arrival, "first_start": first, "completion": comp,
                    "execution_time": exec_time, "waiting": waiting,
                    "turnaround": turnaround, "response": response, "stretch": stretch,
                    "scheduler": t.assigned_scheduler, "subqueue": t.subqueue
                })
        return pd.DataFrame(rows)

    def compute_aggregate_metrics(self):
        df = self.export_task_metrics()
        if df.empty:
            return {}
        metrics = {}
        metrics["avg_turnaround"] = df["turnaround"].mean()
        metrics["median_turnaround"] = df["turnaround"].median()
        metrics["avg_response"] = df["response"].mean()
        metrics["p95_response"] = df["response"].quantile(0.95)
        # Jain fairness on execution_time vs share (simple)
        execs = df["execution_time"].fillna(0).values
        metrics["fairness_index"] = (execs.sum()**2) / (len(execs) * (np.sum(execs**2) + 1e-9))
        # core utilization estimate: sum of runtime on cores / simulation length
        total_time = max(1, self.time)
        utiliz = {}
        for cid in range(self.num_cores):
            # approximate: count RUN events on core
            core_runs = sum(1 for r in self.logs if r["event"] == "RUN" and r["core"] == cid)
            utiliz[cid] = core_runs / total_time
        metrics["core_utilization"] = utiliz
        metrics["context_switches"] = self.context_switches
        total = len(self.task_map)
        completed = len(self.completed_tasks)
        metrics["tasks_total"] = total
        metrics["tasks_completed"] = completed
        print(f"✅ Simulation summary: {completed}/{total} tasks finished.")
        return metrics

