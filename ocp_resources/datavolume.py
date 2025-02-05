from ocp_resources.utils.constants import (
    TIMEOUT_1MINUTE,
    TIMEOUT_2MINUTES,
    TIMEOUT_4MINUTES,
    TIMEOUT_10MINUTES,
    TIMEOUT_10SEC,
)
from ocp_resources.persistent_volume_claim import PersistentVolumeClaim
from ocp_resources.resource import NamespacedResource, Resource
from timeout_sampler import TimeoutExpiredError, TimeoutSampler
from warnings import warn


class DataVolume(NamespacedResource):
    """
    DataVolume object.
    """

    api_group = NamespacedResource.ApiGroup.CDI_KUBEVIRT_IO

    class Status(NamespacedResource.Status):
        BLANK = "Blank"
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
        WAIT_FOR_FIRST_CONSUMER = "WaitForFirstConsumer"
        PENDING_POPULATION = "PendingPopulation"

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
        name=None,
        namespace=None,
        source=None,
        size=None,
        storage_class=None,
        url=None,
        content_type=ContentType.KUBEVIRT,
        access_modes=None,
        cert_configmap=None,
        secret=None,
        client=None,
        volume_mode=None,
        hostpath_node=None,
        source_pvc=None,
        source_namespace=None,
        multus_annotation=None,
        bind_immediate_annotation=None,
        preallocation=None,
        teardown=True,
        yaml_file=None,
        delete_timeout=TIMEOUT_4MINUTES,
        api_name="pvc",
        delete_after_completion=None,
        **kwargs,
    ):
        """
        DataVolume object

        Args:
            name (str): DataVolume name.
            namespace (str): DataVolume namespace.
            source (str): source of DV - upload/http/pvc/registry.
            size (str): DataVolume size - format size+size unit, for example: "5Gi".
            storage_class (str, default: None): storage class name for DataVolume.
            url (str, default: None): url for importing DV, when source is http/registry.
            content_type (str, default: "kubevirt"): DataVolume content type.
            access_modes (str, default: None): DataVolume access mode.
            cert_configmap (str, default: None): name of config map for TLS certificates.
            secret (Secret, default: None): to be set as secretRef.
            client (DynamicClient): DynamicClient to use.
            volume_mode (str, default: None): DataVolume volume mode.
            hostpath_node (str, default: None): Node name to provision the DV on.
            source_pvc (str, default: None): PVC name for when cloning the DV.
            source_namespace (str, default: None): PVC namespace for when cloning the DV.
            multus_annotation (str, default: None): network nad name.
            bind_immediate_annotation (bool, default: None): when WaitForFirstConsumer is set in  StorageClass and DV
            should be bound immediately.
            preallocation (bool, default: None): preallocate disk space.
            teardown (bool, default: True): Indicates if this resource would need to be deleted.
            yaml_file (yaml, default: None): yaml file for the resource.
            delete_timeout (int, default: 4 minutes): timeout associated with delete action.
            api_name (str, default: "pvc"): api used for DV, pvc/storage
            delete_after_completion (str, default: None): annotation for garbage collector - "true"/"false"
        """
        super().__init__(
            name=name,
            namespace=namespace,
            client=client,
            teardown=teardown,
            yaml_file=yaml_file,
            delete_timeout=delete_timeout,
            **kwargs,
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
        self.multus_annotation = multus_annotation
        self.bind_immediate_annotation = bind_immediate_annotation
        self.preallocation = preallocation
        self.api_name = api_name
        self.delete_after_completion = delete_after_completion

    def to_dict(self) -> None:
        super().to_dict()
        if not self.kind_dict and not self.yaml_file:
            self.res.update({
                "spec": {
                    "source": {self.source: {"url": self.url}},
                    self.api_name: {
                        "resources": {"requests": {"storage": self.size}},
                    },
                }
            })
            if self.access_modes:
                self.res["spec"][self.api_name]["accessModes"] = [self.access_modes]
            if self.content_type:
                self.res["spec"]["contentType"] = self.content_type
            if self.storage_class:
                self.res["spec"][self.api_name]["storageClassName"] = self.storage_class
            if self.secret:
                self.res["spec"]["source"][self.source]["secretRef"] = self.secret.name
            if self.volume_mode:
                self.res["spec"][self.api_name]["volumeMode"] = self.volume_mode
            if self.source == "http" or "registry":
                self.res["spec"]["source"][self.source]["url"] = self.url
            if self.cert_configmap:
                self.res["spec"]["source"][self.source]["certConfigMap"] = self.cert_configmap
            if self.source == "upload" or self.source == "blank":
                self.res["spec"]["source"][self.source] = {}
            if self.hostpath_node:
                self.res["metadata"].setdefault("annotations", {}).update({
                    f"{NamespacedResource.ApiGroup.KUBEVIRT_IO}/provisionOnNode": (self.hostpath_node)
                })
            if self.multus_annotation:
                self.res["metadata"].setdefault("annotations", {}).update({
                    f"{NamespacedResource.ApiGroup.K8S_V1_CNI_CNCF_IO}/networks": (self.multus_annotation)
                })
            if self.bind_immediate_annotation:
                self.res["metadata"].setdefault("annotations", {}).update({
                    f"{self.api_group}/storage.bind.immediate.requested": "true"
                })
            if self.source == "pvc":
                self.res["spec"]["source"]["pvc"] = {
                    "name": self.source_pvc or "dv-source",
                    "namespace": self.source_namespace or self.namespace,
                }
            if self.preallocation is not None:
                self.res["spec"]["preallocation"] = self.preallocation
            if self.delete_after_completion:
                self.res["metadata"].setdefault("annotations", {}).update({
                    f"{self.api_group}/storage.deleteAfterCompletion": (self.delete_after_completion)
                })

    def wait_deleted(self, timeout=TIMEOUT_4MINUTES):
        """
        Wait until DataVolume and the PVC created by it are deleted

        Args:
        timeout (int):  Time to wait for the DataVolume and PVC to be deleted.

        Returns:
        bool: True if DataVolume and its PVC are gone, False if timeout reached.
        """
        super().wait_deleted(timeout=timeout)
        return self.pvc.wait_deleted(timeout=timeout)

    def wait(self, timeout=TIMEOUT_10MINUTES, failure_timeout=TIMEOUT_2MINUTES, wait_for_exists_only=False):
        if wait_for_exists_only:
            return super().wait(timeout=timeout)
        else:
            self._check_none_pending_status(failure_timeout=failure_timeout)

            # If DV's status is not Pending, continue with the flow
            self.wait_for_status(status=self.Status.SUCCEEDED, timeout=timeout)
            self.pvc.wait_for_status(status=PersistentVolumeClaim.Status.BOUND, timeout=timeout)

    @property
    def pvc(self):
        return PersistentVolumeClaim(
            client=self.client,
            name=self.name,
            namespace=self.namespace,
        )

    @property
    def scratch_pvc(self):
        scratch_pvc_prefix = self.pvc.prime_pvc.name if self.pvc.use_populator else self.name
        return PersistentVolumeClaim(
            name=f"{scratch_pvc_prefix}-scratch",
            namespace=self.namespace,
            client=self.client,
        )

    def _check_none_pending_status(self, failure_timeout=TIMEOUT_2MINUTES):
        # Avoid waiting for "Succeeded" status if DV's in Pending/None status
        sample = None
        # if garbage collector is enabled, DV will be deleted after success
        try:
            for sample in TimeoutSampler(
                wait_timeout=failure_timeout,
                sleep=TIMEOUT_10SEC,
                func=lambda: self.exists,
            ):
                # If DV status is Pending (or Status is not yet updated) continue to wait, else exit the wait loop
                if sample and (
                    not sample.status
                    or sample.status.phase
                    in [
                        self.Status.PENDING,
                        None,
                    ]
                ):
                    continue
                break
        except TimeoutExpiredError:
            self.logger.error(f"{self.name} status is {sample}")
            raise

    def wait_for_dv_success(
        self,
        timeout=TIMEOUT_10MINUTES,
        failure_timeout=TIMEOUT_2MINUTES,
        dv_garbage_collection_enabled=None,
        stop_status_func=None,
        *stop_status_func_args,
        **stop_status_func_kwargs,
    ):
        """
        Wait until DataVolume succeeded with or without DV Garbage Collection enabled

        Args:
            timeout (int):  Time to wait for the DataVolume to succeed.
            failure_timeout (int): Time to wait for the DataVolume to have not Pending/None status
            dv_garbage_collection_enabled (bool, default: None): DV garbage collection is deprecated and removed in
            v4.19
            stop_status_func (function): function that is called inside the TimeoutSampler
                if it returns True - stop the Sampler and raise TimeoutExpiredError
                Example:
                def dv_is_not_progressing(dv):
                    return True if dv.instance.status.conditions.restartCount > 3 else False

                def test_dv():
                    ...
                    stop_status_func_kwargs = {"dv": dv}
                    dv.wait_for_dv_success(stop_status_func=dv_is_not_progressing, **stop_status_func_kwargs)

        Returns:
            bool: True if DataVolume succeeded.
        """
        self.logger.info(f"Wait DV success for {timeout} seconds")
        self._check_none_pending_status(failure_timeout=failure_timeout)

        sample = None
        status_of_dv_str = f"Status of {self.kind} '{self.name}' in namespace '{self.namespace}':\n"
        try:
            for sample in TimeoutSampler(
                sleep=1,
                wait_timeout=timeout,
                func=lambda: self.exists,
            ):
                if dv_garbage_collection_enabled is not None:
                    warn("garbage collector is deprecated and removed in version v4.19", DeprecationWarning)
                # DV reach success if the status is Succeeded, or if DV garbage collection enabled and the DV does not exist
                if sample and sample.get("status", {}).get("phase") == self.Status.SUCCEEDED:
                    break
                elif sample is None and dv_garbage_collection_enabled:
                    break
                elif stop_status_func and stop_status_func(*stop_status_func_args, **stop_status_func_kwargs):
                    raise TimeoutExpiredError(
                        value=(
                            "Exited on the stop_status_func"
                            f" {stop_status_func.__name__}."
                            f" {status_of_dv_str} {sample.status}"
                        )
                    )
        except TimeoutExpiredError:
            self.logger.error(f"{status_of_dv_str} {sample.status}")
            raise

        # For CSI storage, PVC gets Bound after DV succeeded
        return self.pvc.wait_for_status(status=PersistentVolumeClaim.Status.BOUND, timeout=TIMEOUT_1MINUTE)

    def delete(self, wait=False, timeout=TIMEOUT_4MINUTES, body=None):
        """
        Delete DataVolume

        Args:
            wait (bool): True to wait for DataVolume and PVC to be deleted.
            timeout (int): Time to wait for resources deletion
            body (dict): Content to send for delete()

        Returns:
            bool: True if delete succeeded, False otherwise.
        """
        # if garbage collector is enabled, DV will be deleted after success
        if self.exists:
            return super().delete(wait=wait, timeout=timeout, body=body)
        else:
            return self.pvc.delete(wait=wait, timeout=timeout, body=body)
