# -*- coding: utf-8 -*-


import logging

from resources.utils import TimeoutSampler
from resources.virtual_machine import VirtualMachine
from urllib3.exceptions import ProtocolError

from .resource import TIMEOUT, NamespacedResource


LOGGER = logging.getLogger(__name__)


class VirtualMachineRestore(NamespacedResource):
    """
    VirtualMachineRestore object.
    """

    api_group = NamespacedResource.ApiGroup.SNAPSHOT_KUBEVIRT_IO

    def __init__(
        self, name, namespace, vm_name, snapshot_name, client=None, teardown=True
    ):
        super().__init__(
            name=name, namespace=namespace, client=client, teardown=teardown
        )
        self.vm_name = vm_name
        self.snapshot_name = snapshot_name

    def to_dict(self):
        res = super().to_dict()
        spec = res.setdefault("spec", {})
        spec.setdefault("target", {})[
            "apiGroup"
        ] = NamespacedResource.ApiGroup.KUBEVIRT_IO
        spec["target"]["kind"] = VirtualMachine.kind
        spec["target"]["name"] = self.vm_name
        spec["virtualMachineSnapshotName"] = self.snapshot_name
        return res

    def wait_complete(self, status=True, timeout=TIMEOUT):
        """
        Wait for VirtualMachineRestore to be in status complete

        Args:
            status: Expected status: True for a completed restore operation, False otherwise.
            timeout (int): Time to wait.

        Raises:
            TimeoutExpiredError: If timeout reached.
        """
        LOGGER.info(
            f"Wait for {self.kind} {self.name} status to be complete = {status}"
        )

        samples = TimeoutSampler(
            timeout=timeout,
            sleep=1,
            exceptions=ProtocolError,
            func=self.api().get,
            field_selector=f"metadata.name=={self.name}",
            namespace=self.namespace,
        )
        for sample in samples:
            if sample.items:
                if self.instance.get("status", {}).get("complete", None) == status:
                    return
