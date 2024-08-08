# Generated using https://github.com/RedHatQE/openshift-python-wrapper/blob/main/scripts/resource/README.md

from typing import Any, Dict, Optional

from timeout_sampler import TimeoutSampler, TimeoutWatch
from ocp_resources.constants import PROTOCOL_ERROR_EXCEPTION_DICT, TIMEOUT_4MINUTES
from ocp_resources.resource import NamespacedResource, MissingRequiredArgumentError


class Deployment(NamespacedResource):
    """
    Deployment enables declarative updates for Pods and ReplicaSets.
    """

    api_group: str = NamespacedResource.ApiGroup.APPS

    def __init__(
        self,
        min_ready_seconds: Optional[int] = None,
        paused: Optional[bool] = None,
        progress_deadline_seconds: Optional[int] = None,
        replicas: Optional[int] = None,
        revision_history_limit: Optional[int] = None,
        selector: Optional[Dict[str, Any]] = None,
        strategy: Optional[Dict[str, Any]] = None,
        template: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            min_ready_seconds(int): Minimum number of seconds for which a newly created pod should be ready
              without any of its container crashing, for it to be considered available.
              Defaults to 0 (pod will be considered available as soon as it is ready)

            paused(bool): Indicates that the deployment is paused.

            progress_deadline_seconds(int): The maximum time in seconds for a deployment to make progress before it is
              considered to be failed. The deployment controller will continue to process
              failed deployments and a condition with a ProgressDeadlineExceeded reason
              will be surfaced in the deployment status. Note that progress will not be
              estimated during the time a deployment is paused. Defaults to 600s.

            replicas(int): Number of desired pods. This is a pointer to distinguish between explicit
              zero and not specified. Defaults to 1.

            revision_history_limit(int): The number of old ReplicaSets to retain to allow rollback. This is a pointer
              to distinguish between explicit zero and not specified. Defaults to 10.

            selector(Dict[Any, Any]): Label selector for pods. Existing ReplicaSets whose pods are selected by
              this will be the ones affected by this deployment. It must match the pod
              template's labels.
              A label selector is a label query over a set of resources. The result of
              matchLabels and matchExpressions are ANDed. An empty label selector matches
              all objects. A null label selector matches no objects.

              FIELDS:
                matchExpressions	<[]LabelSelectorRequirement>
                  matchExpressions is a list of label selector requirements. The requirements
                  are ANDed.

                matchLabels	<map[string]string>
                  matchLabels is a map of {key,value} pairs. A single {key,value} in the
                  matchLabels map is equivalent to an element of matchExpressions, whose key
                  field is "key", the operator is "In", and the values array contains only
                  "value". The requirements are ANDed.

            strategy(Dict[Any, Any]): The deployment strategy to use to replace existing pods with new ones.
              DeploymentStrategy describes how to replace existing pods with new ones.

              FIELDS:
                rollingUpdate	<RollingUpdateDeployment>
                  Rolling update config params. Present only if DeploymentStrategyType =
                  RollingUpdate.

                type	<string>
                  Type of deployment. Can be "Recreate" or "RollingUpdate". Default is
                  RollingUpdate.

                  Possible enum values:
                   - `"Recreate"` Kill all existing pods before creating new ones.
                   - `"RollingUpdate"` Replace the old ReplicaSets by new one using rolling
                  update i.e gradually scale down the old ReplicaSets and scale up the new
                  one.

            template(Dict[Any, Any]): Template describes the pods that will be created. The only allowed
              template.spec.restartPolicy value is "Always".
              PodTemplateSpec describes the data a pod should have when created from a
              template

              FIELDS:
                metadata	<ObjectMeta>
                  Standard object's metadata. More info:
                  https://git.k8s.io/community/contributors/devel/sig-architecture/api-conventions.md#metadata

                spec	<PodSpec>
                  Specification of the desired behavior of the pod. More info:
                  https://git.k8s.io/community/contributors/devel/sig-architecture/api-conventions.md#spec-and-status

        """
        super().__init__(**kwargs)

        self.min_ready_seconds = min_ready_seconds
        self.paused = paused
        self.progress_deadline_seconds = progress_deadline_seconds
        self.replicas = replicas
        self.revision_history_limit = revision_history_limit
        self.selector = selector
        self.strategy = strategy
        self.template = template

    def to_dict(self) -> None:
        super().to_dict()

        if not self.yaml_file:
            if not all([
                self.selector,
                self.template,
            ]):
                raise MissingRequiredArgumentError(argument="selector, template")

            self.res["spec"] = {}
            _spec = self.res["spec"]

            self.res["selector"] = self.selector
            self.res["template"] = self.template

            if self.min_ready_seconds:
                _spec["minReadySeconds"] = self.min_ready_seconds

            if self.paused is not None:
                _spec["paused"] = self.paused

            if self.progress_deadline_seconds:
                _spec["progressDeadlineSeconds"] = self.progress_deadline_seconds

            if self.replicas:
                _spec["replicas"] = self.replicas

            if self.revision_history_limit:
                _spec["revisionHistoryLimit"] = self.revision_history_limit

            if self.strategy:
                _spec["strategy"] = self.strategy

    def scale_replicas(self, replica_count=int):
        """
        Update replicas in deployment.

        Args:
            replica_count (int): Number of replicas.

        Returns:
            Deployment is updated successfully
        """
        super().to_dict()
        self.res.update({"spec": {"replicas": replica_count}})

        self.logger.info(f"Set deployment replicas: {replica_count}")
        return self.update(resource_dict=self.res)

    def wait_for_replicas(self, deployed: bool = True, timeout: int = TIMEOUT_4MINUTES):
        """
        Wait until all replicas are updated.

        Args:
            deployed (bool): True for replicas deployed, False for no replicas.
            timeout (int): Time to wait for the deployment.

        Raises:
            TimeoutExpiredError: If not availableReplicas is equal to replicas.
        """
        self.logger.info(f"Wait for {self.kind} {self.name} to be deployed: {deployed}")

        timeout_watcher = TimeoutWatch(timeout=timeout)
        for sample in TimeoutSampler(
            wait_timeout=timeout,
            sleep=1,
            func=lambda: self.exists,
        ):
            if sample:
                break

        samples = TimeoutSampler(
            wait_timeout=timeout_watcher.remaining_time(),
            sleep=1,
            exceptions_dict=PROTOCOL_ERROR_EXCEPTION_DICT,
            func=lambda: self.instance,
        )
        for sample in samples:
            if sample:
                status = sample.status

                spec_replicas = sample.spec.replicas
                total_replicas = status.replicas or 0
                updated_replicas = status.updatedReplicas or 0
                available_replicas = status.availableReplicas or 0
                ready_replicas = status.readyReplicas or 0

                if (
                    (deployed and spec_replicas)
                    and spec_replicas == updated_replicas == available_replicas == ready_replicas
                ) or not (deployed or spec_replicas or total_replicas):
                    return
