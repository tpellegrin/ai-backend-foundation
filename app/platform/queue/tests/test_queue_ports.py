# ruff: noqa: S101
from collections.abc import Mapping
from typing import Any

import pytest

from app.platform.queue.ports import EnqueueOptions, JobId, JobStatus, TaskQueue


class InMemoryTaskQueueFake:
    """An in-memory fake implementation of the TaskQueue port."""

    def __init__(self) -> None:
        self.jobs: dict[JobId, JobStatus] = {}
        self.payloads: dict[JobId, Mapping[str, Any]] = {}
        self.counter = 0

    async def enqueue(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        options: EnqueueOptions | None = None,
    ) -> JobId:
        self.counter += 1
        job_id = JobId(f"job-{self.counter}")
        self.jobs[job_id] = "queued"
        self.payloads[job_id] = payload
        return job_id

    async def status(self, job_id: JobId) -> JobStatus:
        return self.jobs.get(job_id, "failed")


@pytest.mark.unit
def test_task_queue_protocol_satisfiability() -> None:
    """Assert that InMemoryTaskQueueFake satisfies the TaskQueue protocol."""
    fake = InMemoryTaskQueueFake()
    assert isinstance(fake, TaskQueue)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_in_memory_task_queue_fake_behavior() -> None:
    """Sanity check that the fake actually works as expected."""
    fake = InMemoryTaskQueueFake()
    payload = {"file_id": "123"}

    job_id = await fake.enqueue("ingest_document", payload)
    assert job_id == JobId("job-1")
    assert await fake.status(job_id) == "queued"

    # Simulate job running
    fake.jobs[job_id] = "running"
    assert await fake.status(job_id) == "running"

    # Simulate job completion
    fake.jobs[job_id] = "done"
    assert await fake.status(job_id) == "done"
