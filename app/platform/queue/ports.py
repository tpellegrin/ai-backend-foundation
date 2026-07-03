from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, NewType, Protocol, runtime_checkable

JobId = NewType("JobId", str)
JobStatus = Literal["queued", "running", "done", "failed"]


@dataclass(frozen=True)
class EnqueueOptions:
    """Options for enqueuing a background task."""

    queue_name: str | None = None
    delay_s: int | None = None
    max_retries: int = 3
    idempotency_key: str | None = None


@runtime_checkable
class TaskQueue(Protocol):
    """
    Cross-cutting task queue port.

    Used to enqueue background jobs (e.g. document ingestion).
    """

    async def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        options: EnqueueOptions | None = None,
    ) -> JobId:
        """
        Enqueue a new job.

        Args:
            name: The name of the task to execute.
            payload: The data to pass to the task.
            options: Optional execution settings.

        Returns:
            The unique identifier of the enqueued job.
        """
        ...

    async def status(self, job_id: JobId) -> JobStatus:
        """
        Retrieve the current status of a job.

        Args:
            job_id: The ID of the job to check.

        Returns:
            The current status of the job.
        """
        ...
