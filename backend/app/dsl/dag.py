"""Python DSL for defining workflow DAGs.

Example usage:

    from app.dsl.dag import DAG, Task

    with DAG("etl_pipeline", description="Daily ETL") as dag:
        extract = Task("extract", callable_name="tasks.extract_data", kwargs={"source": "s3"})
        transform = Task("transform", callable_name="tasks.transform_data")
        load = Task("load", callable_name="tasks.load_to_warehouse")

        extract >> transform >> load

    # Serialize for storage:
    dag.to_dict()
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass
class Task:
    """A single task node in a DAG."""

    task_id: str
    callable_name: str
    args: list[Any] = field(default_factory=list)
    kwargs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 3600

    _dag: DAG | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._dag is not None:
            self._dag.add_task(self)

    # Operator overloads for chaining: extract >> transform
    def __rshift__(self, other: Task | list[Task]) -> Task | list[Task]:
        targets = other if isinstance(other, list) else [other]
        for t in targets:
            if self.task_id not in t.depends_on:
                t.depends_on.append(self.task_id)
        return other

    def __rrshift__(self, other: list[Task]) -> Self:
        """Support ``[a, b] >> c`` fan-in pattern."""
        for s in other:
            if s.task_id not in self.depends_on:
                self.depends_on.append(s.task_id)
        return self

    def __lshift__(self, other: Task | list[Task]) -> Self:
        sources = other if isinstance(other, list) else [other]
        for s in sources:
            if s.task_id not in self.depends_on:
                self.depends_on.append(s.task_id)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "callable_name": self.callable_name,
            "args": self.args,
            "kwargs": self.kwargs,
            "depends_on": self.depends_on,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "timeout_seconds": self.timeout_seconds,
        }


class DAG:
    """Directed Acyclic Graph of tasks.

    Can be used as a context manager so tasks auto-register themselves.
    """

    # Class-level stack for context-manager nesting.
    _context_stack: list[DAG] = []

    def __init__(
        self,
        name: str,
        description: str | None = None,
        cron_schedule: str | None = None,
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        default_timeout: int = 3600,
        tags: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.cron_schedule = cron_schedule
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.default_timeout = default_timeout
        self.tags = tags or {}
        self._tasks: dict[str, Task] = {}

    # Context manager -------------------------------------------------------

    def __enter__(self) -> DAG:
        DAG._context_stack.append(self)
        return self

    def __exit__(self, *args: object) -> None:
        DAG._context_stack.pop()

    @classmethod
    def get_current(cls) -> DAG | None:
        return cls._context_stack[-1] if cls._context_stack else None

    # Task management -------------------------------------------------------

    def add_task(self, task: Task) -> None:
        if task.task_id in self._tasks:
            raise ValueError(f"Duplicate task_id: {task.task_id}")
        task._dag = self
        self._tasks[task.task_id] = task

    @property
    def tasks(self) -> dict[str, Task]:
        return dict(self._tasks)

    # Topological sort (Kahn's algorithm) -----------------------------------

    def topological_sort(self) -> list[str]:
        """Return task IDs in dependency-respecting order.

        Raises ValueError if the graph contains a cycle.
        """
        in_degree: dict[str, int] = {tid: 0 for tid in self._tasks}
        adjacency: dict[str, list[str]] = {tid: [] for tid in self._tasks}

        for tid, task in self._tasks.items():
            for dep in task.depends_on:
                if dep not in self._tasks:
                    raise ValueError(f"Task '{tid}' depends on unknown task '{dep}'")
                adjacency[dep].append(tid)
                in_degree[tid] += 1

        queue: deque[str] = deque(tid for tid, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._tasks):
            raise ValueError("DAG contains a cycle")

        return order

    def get_ready_tasks(self, completed: set[str]) -> list[str]:
        """Return task IDs whose dependencies are all in *completed*."""
        ready: list[str] = []
        for tid, task in self._tasks.items():
            if tid in completed:
                continue
            if all(dep in completed for dep in task.depends_on):
                ready.append(tid)
        return ready

    # Serialization ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self._tasks.values()],
        }

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any], **kwargs: Any) -> DAG:
        dag = cls(name=name, **kwargs)
        for t_data in data.get("tasks", []):
            task = Task(**t_data)
            dag.add_task(task)
        return dag

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[str] = []
        if not self._tasks:
            errors.append("DAG has no tasks")
        # Check for cycles
        try:
            self.topological_sort()
        except ValueError as exc:
            errors.append(str(exc))
        # Check for missing dependencies
        all_ids = set(self._tasks.keys())
        for tid, task in self._tasks.items():
            for dep in task.depends_on:
                if dep not in all_ids:
                    errors.append(f"Task '{tid}' depends on unknown task '{dep}'")
        return errors
