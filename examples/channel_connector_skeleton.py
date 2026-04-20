from __future__ import annotations

from finkernel.storage.models import WorkflowRequestModel


class ExampleChannelClient:
    def send_confirmation(self, workflow_request: WorkflowRequestModel) -> None:
        raise NotImplementedError

    def send_status_update(self, workflow_request: WorkflowRequestModel, message: str) -> None:
        raise NotImplementedError
