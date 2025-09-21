import pytest
from src.scheduler.task import Task
from src.scheduler.ai_scheduler import AIScheduler

def test_task_creation():
    """Check if Task initializes correctly."""
    t = Task(pid=1, arrival_time=0, burst_time=10, priority=5, resource_type="CPU")
    assert t.pid == 1
    assert t.burst_time == 10
    assert t.resource_type == "CPU"

def test_ai_scheduler_assignment():
    """Check if AIScheduler assigns correct policy based on interactivity class."""
    ai = AIScheduler()
    # Fake tasks with different interactivity labels
    rt_task = Task(pid=2, arrival_time=0, burst_time=5, priority=1, resource_type="CPU", interactivity="Realtime")
    int_task = Task(pid=3, arrival_time=0, burst_time=5, priority=1, resource_type="CPU", interactivity="Interactive")
    batch_task = Task(pid=4, arrival_time=0, burst_time=5, priority=1, resource_type="CPU", interactivity="Batch")

    assert ai.assign_scheduler(rt_task) == "FIFO"
    assert ai.assign_scheduler(int_task) == "RR"
    assert ai.assign_scheduler(batch_task) == "CFS"
