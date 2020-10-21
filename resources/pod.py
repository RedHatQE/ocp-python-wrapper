import json
import logging

import kubernetes

from . import utils
from .node import Node
from .resource import NamespacedResource


LOGGER = logging.getLogger(__name__)


class ExecOnPodError(Exception):
    def __init__(self, command, rc, out, err):
        self.cmd = command
        self.rc = rc
        self.out = out
        self.err = err

    def __str__(self):
        return (
            f"Command execution failure: "
            f"{self.cmd}, "
            f"RC: {self.rc}, "
            f"OUT: {self.out}, "
            f"ERR: {self.err}"
        )


class Pod(NamespacedResource):
    """
    Pod object, inherited from Resource.
    """

    api_version = NamespacedResource.ApiVersion.V1

    class Status(NamespacedResource.Status):
        RUNNING = "Running"
        CRASH_LOOPBACK_OFF = "CrashLoopBackOff"

    def __init__(self, name, namespace, client=None, teardown=True):
        super().__init__(
            name=name, namespace=namespace, client=client, teardown=teardown,
        )
        self._kube_api = kubernetes.client.CoreV1Api(api_client=self.client.client)

    @property
    def containers(self):
        """
        Get Pod containers

        Returns:
            list: List of Pod containers
        """
        return self.instance.spec.containers

    def execute(self, command, timeout=60, container=None):
        """
        Run command on Pod

        Args:
            command (list): Command to run.
            timeout (int): Time to wait for the command.
            container (str): Container name where to exec the command.

        Returns:
            str: Command output.

        Raises:
            ExecOnPodError: If the command failed.
        """
        LOGGER.info(f"Execute {command} on {self.name} ({self.node().name})")
        resp = kubernetes.stream.stream(
            func=self._kube_api.connect_get_namespaced_pod_exec,
            name=self.name,
            namespace=self.namespace,
            command=command,
            container=container or self.containers[0].name,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        timeout_watch = utils.TimeoutWatch(timeout=timeout)
        while resp.is_open():
            resp.run_forever(timeout=2)
            try:
                error_channel = json.loads(
                    resp.read_channel(kubernetes.stream.ws_client.ERROR_CHANNEL)
                )
                break
            except json.decoder.JSONDecodeError:
                # Check remaining time, in order to throw exception
                # if reamining time reached zero
                _ = timeout_watch.remaining_time()

        rcstring = error_channel.get("status")
        if rcstring is None:
            raise ExecOnPodError(
                command=command, rc=-1, out="", err="stream resp is closed"
            )

        stdout = resp.read_stdout(timeout=5)
        stderr = resp.read_stderr(timeout=5)

        if rcstring == "Success":
            return stdout

        returncode = [
            int(cause["message"])
            for cause in error_channel["details"]["causes"]
            if cause["reason"] == "ExitCode"
        ][0]

        raise ExecOnPodError(command=command, rc=returncode, out=stdout, err=stderr)

    def log(self, **kwargs):
        """
        Get Pod logs

        Returns:
            str: Pod logs.
        """
        return self._kube_api.read_namespaced_pod_log(
            name=self.name, namespace=self.namespace, **kwargs
        )

    def node(self, client=None):
        """
        Get the node name where the Pod is running

        Returns:
            Node: Node
        """
        return Node(client=client or self.client, name=self.instance.spec.nodeName,)

    @property
    def ip(self):
        return self.instance.status.podIP
