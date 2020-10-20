# -*- coding: utf-8 -*-

import logging

from .persistent_volume_claim import PersistentVolumeClaim
from .resource import TIMEOUT, NamespacedResource, Resource


LOGGER = logging.getLogger(__name__)


class DataVolume(NamespacedResource):
    """
    DataVolume object.
    """

    api_group = NamespacedResource.ApiGroup.CDI_KUBEVIRT_IO

    class Status(NamespacedResource.Status):
        BLANK = "Blank"
        PENDING = "Pending"
        PVC_BOUND = "PVCBound"
        IMPORT_SCHEDULED = "ImportScheduled"
        ClONE_SCHEDULED = "CloneScheduled"
        UPLOAD_SCHEDULED = "UploadScheduled"
        IMPORT_IN_PROGRESS = "ImportInProgress"
        CLONE_IN_PROGRESS = "CloneInProgress"
        UPLOAD_IN_PROGRESS = "UploadInProgress"
        SNAPSHOT_FOR_SMART_CLONE_IN_PROGRESS = "SnapshotForSmartCloneInProgress"
        SMART_CLONE_PVC_IN_PROGRESS = "SmartClonePVCInProgress"
        UPLOAD_READY = "UploadReady"
        UNKNOWN = "Unknown"

    class AccessMode:
        """
        AccessMode object.
        """

        RWO = "ReadWriteOnce"
        ROX = "ReadOnlyMany"
        RWX = "ReadWriteMany"

    class ContentType:
        """
        ContentType object
        """

        KUBEVIRT = "kubevirt"
        ARCHIVE = "archive"

    class VolumeMode:
        """
        VolumeMode object
        """

        BLOCK = "Block"
        FILE = "Filesystem"

    class Condition:
        class Type:
            READY = "Ready"
            BOUND = "Bound"
            RUNNING = "Running"

        class Status(Resource.Condition.Status):
            UNKNOWN = "Unknown"

    def __init__(
        self,
        name,
        namespace,
        source=None,
        size=None,
        storage_class=None,
        url=None,
        content_type=ContentType.KUBEVIRT,
        access_modes=AccessMode.RWO,
        cert_configmap=None,
        secret=None,
        client=None,
        volume_mode=VolumeMode.FILE,
        hostpath_node=None,
        source_pvc=None,
        source_namespace=None,
        teardown=True,
        override_client=True,
    ):
        super().__init__(
            name=name,
            namespace=namespace,
            client=client,
            teardown=teardown,
            override_client=override_client,
        )
        self.source = source
        self.url = url
        self.cert_configmap = cert_configmap
        self.secret = secret
        self.content_type = content_type
        self.size = size
        self.access_modes = access_modes
        self.storage_class = storage_class
        self.volume_mode = volume_mode
        self.hostpath_node = hostpath_node
        self.source_pvc = source_pvc
        self.source_namespace = source_namespace

    def wait_deleted(self, timeout=TIMEOUT):
        """
        Wait until DataVolume and the PVC created by it are deleted

        Args:
        timeout (int):  Time to wait for the DataVolume and PVC to be deleted.

        Returns:
        bool: True if DataVolume and its PVC are gone, False if timeout reached.
        """
        super().wait_deleted(timeout=timeout)
        return self.pvc.wait_deleted(timeout=timeout)

    def wait(self, timeout=600):
        self.wait_for_status(status=self.Status.SUCCEEDED, timeout=timeout)
        self.pvc.wait_for_status(
            status=PersistentVolumeClaim.Status.BOUND, timeout=timeout
        )

    @property
    def pvc(self):
        return PersistentVolumeClaim(
            client=self.client,
            name=self.name,
            namespace=self.namespace,
            override_client=self.override_client,
        )

    @property
    def scratch_pvc(self):
        return PersistentVolumeClaim(
            client=self.client,
            name=f"{self.name}-scratch",
            namespace=self.namespace,
            override_client=self.override_client,
        )

    def to_dict(self):
        res = super()._base_body()
        res.update(
            {
                "spec": {
                    "source": {self.source: {"url": self.url}},
                    "pvc": {
                        "accessModes": [self.access_modes],
                        "resources": {"requests": {"storage": self.size}},
                    },
                }
            }
        )
        if self.content_type:
            res["spec"]["contentType"] = self.content_type
        if self.storage_class:
            res["spec"]["pvc"]["storageClassName"] = self.storage_class
        if self.secret:
            res["spec"]["source"][self.source]["secretRef"] = self.secret.name
        if self.volume_mode:
            res["spec"]["pvc"]["volumeMode"] = self.volume_mode
        if self.source == "http" or "registry":
            res["spec"]["source"][self.source]["url"] = self.url
        if self.cert_configmap:
            res["spec"]["source"][self.source]["certConfigMap"] = self.cert_configmap
        if self.source == "upload" or self.source == "blank":
            res["spec"]["source"][self.source] = {}
        if self.hostpath_node:
            res["metadata"]["annotations"] = {
                "kubevirt.io/provisionOnNode": self.hostpath_node
            }
        if self.source == "pvc":
            res["spec"]["source"]["pvc"] = {
                "name": self.source_pvc or "dv-source",
                "namespace": self.source_namespace or self.namespace,
            }

        return res
