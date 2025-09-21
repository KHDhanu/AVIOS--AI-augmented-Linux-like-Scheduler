# ------------------------------
# AI Integrated with Linux Scheduler
# ------------------------------
import heapq
import itertools
from collections import deque, defaultdict
import pandas as pd
import numpy as np
import time

class AIScheduler:

    def __init__(self, num_cores=4, core_priority_order=None,
                 rr_quantum=100, cfs_base_slice=4, seed=42, models=None, encoders=None):
        self.num_cores = num_cores
        self.rr_quantum = int(rr_quantum)
        self.cfs_base_slice = float(cfs_base_slice)  # used as base multiplier
        self.insertion_counter = itertools.count()
        self.seed = seed

        # -----------------------------
        # ML Models + Encoders
        # -----------------------------
        self.models = models if models else {}
        self.encoders = encoders if encoders else {}

        if models:
           self.models = models
        else:
           self.models = {
               "resource": rf_resource_model,
               "interactivity": xgb_inter_model,
               "priority": rf_priority_model,
               "execution": rf_execution_model
           }

        if encoders:
           self.encoders = encoders
        else:
           self.encoders = {
              "resource": le_resource,
              "interactivity": le_inter,
              "priority": le_priority,
              "execution": le_execution
           }

        self.feature_lists = {
            "resource": json.load(open("resource_features.json")),
            "interactivity": json.load(open("interactivity_features.json")),
            "priority": json.load(open("priority_features.json")),
            "execution": json.load(open("execution_features.json"))
        }

        # per-core priority order
        self.core_priority_order = core_priority_order or {
            cid: ["FIFO", "RR", "CFS", "IDLE"] for cid in range(num_cores)
        }

        self.queues = {
            "FIFO": {"fifo_1": deque()},
            "RR": {"rr_1": deque()},
            "CFS": {"cfs_1": [] },   # min-heaps of (vruntime, counter, pid, task)
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
        """
        AI-aware admit:
         - run ML classification + scoring (preserved exactly),
         - estimate remaining,
         - assign scheduler/subqueue (kept as your mapping),
         - set vruntime/weight from features if available,
         - set RR initial quantum if needed,
         - enqueue and log (Linux-style).
        """
        if current_time is None:
            current_time = self.time

        # Ensure arrival_time present
        if getattr(task, "arrival_time", None) is None:
            task.arrival_time = int(current_time)

        # Register in task_map
        self.task_map[task.pid] = task

        # ---- AI classification + scoring (preserve your logic) ----
        # This may set: resource_type, interactivity, priority_class, execution_class
        self._classify_task(task)

        # numeric labels (returns tuple) — calling for completeness (you keep original logic)
        try:
            self._map_numeric_labels(task.resource_type, task.interactivity, task.execution_class, task.priority_class)
        except Exception:
            pass

        # compute combined subqueue score (sets task.subqueue_score)
        try:
            self._compute_subqueue_score(task)
        except Exception:
            pass

        # Estimate remaining if not already present (keep conservative fallback)
        if getattr(task, "remaining", None) is None or task.remaining == 0:
            # prefer Total_Time_Ticks feature, else fallback to task.total_time or 1
            task.remaining = int(task.features.get("Total_Time_Ticks", getattr(task, "total_time", 1) or 1))

        # ---- Assign scheduler/subqueue (your mapping kept) ----
        # NOTE: preserve explicit scheduling policy for SCHED_RR too (Linux-like)
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
            self._assign_scheduler_and_subqueue(task)

        # ---- Ensure vruntime and weight (from features when available) ----
        task.vruntime = float(task.features.get("se.vruntime", getattr(task, "vruntime", 0.0) or 0.0))
        task.weight = float(task.features.get("se.load.weight", getattr(task, "weight", 1024.0) or 1024.0))

        # ---- For RR, set an initial quantum (Linux-like) ----
        if getattr(task, "assigned_scheduler", None) == "RR":
            # task.quantum = max(self.min_granularity, int(getattr(self, "rr_quantum", 5)))
            base_score = 2.5
            max_score = 3.15
            base_quantum = 100
            max_quantum = 200
            score = float(getattr(task, "subqueue_score", 2.0))
            if score <= base_score:
                 task.quantum = base_quantum
            elif score >= max_score:
                task.quantum = max_quantum
            else:
               # Linear growth between base_score and max_score
                frac = (score - base_score) / (max_score - base_score)
                task.quantum = int(base_quantum + frac * (max_quantum - base_quantum))
        else:
            # leave quantum to be computed at dispatch for CFS/FIFO (or None)
            task.quantum = getattr(task, "quantum", None)

        # final enqueue + log (use existing logging helper)
        try:
            self._log("ADMIT", task)
        except Exception:
            # fallback to appending a simple log row if _log is not available
            self.logs.append({"time": current_time, "event": "ADMIT", "pid": getattr(task, "pid", None)})

        self._enqueue_task(task)

    # --------------------
    # AI helpers
    # --------------------

    def _classify_task(self, task):
        """
        Run ML models to classify task into 4 categories.
        Kept identical to your implementation (safe fallbacks included).
        """
        try:
           # Resource
           X_res = task.get_feature_vector("resource")
           X_res = pd.DataFrame(X_res, columns=self.feature_lists["resource"])
           pred_res = self.models["resource"].predict(X_res)[0]
           try:
              task.resource_type = self.encoders["resource"].inverse_transform([pred_res])[0]
           except Exception:
              task.resource_type = "Mixed"  # fallback safe default

           # Interactivity
           X_int = task.get_feature_vector("interactivity")
           X_int = pd.DataFrame(X_int, columns=self.feature_lists["interactivity"])
           pred_int = self.models["interactivity"].predict(X_int)[0]
           try:
              task.interactivity = self.encoders["interactivity"].inverse_transform([pred_int])[0]
           except Exception:
              task.interactivity = "Other"

           # Priority
           X_pri = task.get_feature_vector("priority")
           X_pri = pd.DataFrame(X_pri, columns=self.feature_lists["priority"])
           pred_pri = self.models["priority"].predict(X_pri)[0]
           try:
              task.priority_class = self.encoders["priority"].inverse_transform([pred_pri])[0]
           except Exception:
              task.priority_class = "Medium"

           # Execution
           X_exe = task.get_feature_vector("execution")
           X_exe = pd.DataFrame(X_exe, columns=self.feature_lists["execution"])
           pred_exe = self.models["execution"].predict(X_exe)[0]
           try:
              task.execution_class = self.encoders["execution"].inverse_transform([pred_exe])[0]
           except Exception:
              task.execution_class = "Medium"

        except Exception as e:
               print(f"⚠️ Classification failed for PID={getattr(task,'pid',None)}: {e}")
               task.resource_type = task.resource_type or "Mixed"
               task.interactivity = task.interactivity or "Other"
               task.priority_class = task.priority_class or "Medium"
               task.execution_class = task.execution_class or "Medium"

    def _map_numeric_labels(self, resource, inter, exec_c, priority):
        Rmap = {"CPU-bound": 3, "Mixed": 2, "IO-bound": 1}
        Imap = {"Real-time": 4, "Interactive": 3, "Other": 2, "Background": 1.5, "Batch": 1}
        Emap = {"Short": 3, "Medium": 2, "Long": 1}
        Pmap = {"High": 3, "Medium": 2, "Low": 1}
        return (
            Rmap.get(resource, 2),
            Imap.get(inter, 2),
            Emap.get(exec_c, 2),
            Pmap.get(priority, 2)
        )

    def _compute_subqueue_score(self, task):
        Rnum, Inum, Enum, Pnum = self._map_numeric_labels(
            task.resource_type, task.interactivity, task.execution_class, task.priority_class
        )
        w_r, w_i, w_e, w_p = 0.2, 0.35, 0.2, 0.3
        task.subqueue_score = float(w_r*Rnum + w_i*Inum + w_e*Enum + w_p*Pnum)
        return task.subqueue_score

    def _assign_scheduler_and_subqueue(self, task):
        # Strict policy overrides
        sched_pol = str(task.features.get("Scheduling_Policy", "")).upper()
        if sched_pol == "SCHED_FIFO":
            task.assigned_scheduler = "FIFO"; task.subqueue = "fifo_1"; return
        if sched_pol == "SCHED_IDLE":
            task.assigned_scheduler = "IDLE"; task.subqueue = "idle"; return

        score = float(getattr(task, "subqueue_score", 0.0))
        rt, inter, exec_t, prio = task.resource_type, task.interactivity, task.execution_class, task.priority_class

        if inter == "Real-time":
            task.assigned_scheduler = "FIFO"
            task.subqueue = "fifo_1"
            return

        elif (inter == "Interactive" and exec_t == "Short" and (prio in ["High"])) or score > 2.6:
            task.assigned_scheduler = "RR"
            task.subqueue = "rr_1"
            return

        else :
            task.assigned_scheduler = "CFS"
            task.subqueue = "cfs_1"
            return

    # --------------------
    # Core pick & dispatch
    # --------------------
    def _pick_task_for_core(self, core_id):
        """
        Linux-like: iterate per-core priority order, pick first non-empty subqueue.
        Returns (sched, subq) or (None, None).
        """
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

            # task.quantum = max(self.min_granularity, base_slice)
            score = float(getattr(task, "subqueue_score", 2.0))
            exec_class = getattr(task, "execution_class", "Medium")
            exec_factor_map = {"Short": 1.0, "Medium": 1.5, "Long": 2.0}
            exec_scale = exec_factor_map.get(exec_class, 1.5)
            score_scale = 1.0 + 0.2 * (score - 2.0)  # light bonus, e.g. +20% at high score
            quanta = base_slice * exec_scale * score_scale
            task.quantum = max(self.min_granularity, int(quanta))

        elif sched == "FIFO":
            # FIFO runs until completion (set quantum = remaining)
            task.quantum = max(1, int(task.remaining))
        elif sched == "RR":
            # task.quantum = max(self.min_granularity, int(self.rr_quantum))
            base_score = 2.5
            max_score = 3.15
            base_quantum = 100
            max_quantum = 200
            score = float(getattr(task, "subqueue_score", 2.0))
            if score <= base_score:
                 task.quantum = base_quantum
            elif score >= max_score:
                task.quantum = max_quantum
            else:
               # Linear growth between base_score and max_score
                frac = (score - base_score) / (max_score - base_score)
                task.quantum = int(base_quantum + frac * (max_quantum - base_quantum))

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
        # task.vruntime += float(delta) * (self.NICE0_WEIGHT / float(task.weight))
        base_inc = float(delta) * (self.NICE0_WEIGHT / float(task.weight))
        score = float(getattr(task, "subqueue_score", 2.0))
        score_scale = 2.0 / max(0.5, score)   # >2 score → smaller increment
        task.vruntime += base_inc * score_scale

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

