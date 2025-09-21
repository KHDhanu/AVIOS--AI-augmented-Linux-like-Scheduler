# ================================
# PART 2: Task Class Definition
# ================================
import uuid
import numpy as np

class Task:
    """Represents a process/task in our AI Scheduler."""

    def __init__(self, row):
        # --- Original features (dict for ML models) ---
        if hasattr(row, "to_dict"):
            self.features = row.to_dict()
        elif isinstance(row, dict):
            self.features = dict(row)
        else:
            try:
                self.features = dict(row)
            except Exception:
                self.features = {}

        # --- Identity ---
        self.pid = self.features.get("PID")
        self.name = self.features.get("Name", f"T{self.pid}")

        # Prefer Linux CFS runtime if available, else fallback
        sum_exec = float(self.features.get("se.sum_exec_runtime", 0))
        total_ticks = float(self.features.get("Total_Time_Ticks", 0))

        # If Total_Time_Ticks is 0, fallback to sum_exec_runtime
        self.total_time = int(total_ticks if total_ticks > 0 else sum_exec)
        self.remaining = self.total_time
        self.arrival_time = int(self.features.get("Arrival_Sec", 0))

        # --- Classification labels (to be predicted later) ---
        self.resource_type = None
        self.interactivity = None
        self.priority_class = None
        self.execution_class = None

        # --- Scheduling assignments ---
        self.subqueue_score = None
        self.assigned_scheduler = None   # FIFO / RR / CFS / IDLE
        self.subqueue = None

        # --- Runtime execution info ---
        self.quantum = None
        self.total_run = 0
        self.first_start = None
        self.completion_time = None

        # --- CFS-specific ---
        self.vruntime = float(self.features.get("se.vruntime", 0))
        self.weight = float(self.features.get("se.load.weight", 1024))

        # --- Affinity ---
        self.last_core = None

        # --- Logging ID (optional, unique) ---
        self.uid = str(uuid.uuid4())[:8]


    @classmethod
    def from_row(cls, row):
        # Accept Series or dict
        if hasattr(row, "to_dict"):
            return cls(row)
        else:
            return cls(row)

    def get_feature_vector(self, category: str):
        """Return numpy array [1, n_features] in the right order."""
        if category == "resource":
            feats_list = {f: self.features.get(f, 0) for f in resource_feats}
        elif category == "interactivity":
            feats_list = {f: self.features.get(f, 0) for f in interactivity_feats}
        elif category == "priority":
            feats_list = {f: self.features.get(f, 0) for f in priority_feats}
        elif category == "execution":
             feats_list = {f: self.features.get(f, 0) for f in execution_feats}
        else:
            raise ValueError(f"Unknown feature category: {category}")

        values = []
        for f in feats_list:
            val = self.features.get(f, 0)

            # Handle mappings
            if f == "Scheduling_Policy":
                mapping = {"SCHED_OTHER": 0, "SCHED_FIFO": 1, "SCHED_RR": 2, "SCHED_IDLE": 3}
                val_upper = str(val).upper() if val is not None else ""
                val = mapping.get(val_upper, 0)
            elif f == "State":
                mapping = {"RUNNING": 0, "SLEEPING": 1, "STOPPED": 2, "ZOMBIE": 3}
                val_upper = str(val).upper() if val is not None else ""
                val = mapping.get(val_upper, 0)
            else:
                try:
                    val = float(val)
                except Exception:
                    val = 0.0

            values.append(val)

        return np.array([values])  # keep 2D shape for sklearn

    def to_log_dict(self, current_time=None, state="READY"):
        """Return dict snapshot for logging."""
        return {
            "timestamp": current_time,
            "pid": self.pid,
            "name": self.name,
            "arrival_time": self.arrival_time,
            "assigned_scheduler": self.assigned_scheduler,
            "subqueue": self.subqueue,
            "labels": {
                "resource": self.resource_type,
                "interactivity": self.interactivity,
                "priority": self.priority_class,
                "execution": self.execution_class,
            },
            "subqueue_score": self.subqueue_score,
            "quantum": self.quantum,
            "remaining": self.remaining,
            "total_run": self.total_run,
            "first_start": self.first_start,
            "completion_time": self.completion_time,
            "vruntime": self.vruntime,
            "weight": self.weight,
            "last_core": self.last_core,
            "state": state
        }

    def __repr__(self):
        return (f"<Task pid={self.pid} name={self.name} "
                f"arr={self.arrival_time} sched={self.assigned_scheduler} "
                f"subq={self.subqueue} remaining={self.remaining}>")
