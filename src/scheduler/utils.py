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
        
