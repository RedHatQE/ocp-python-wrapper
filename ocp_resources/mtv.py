import logging

from ocp_resources.utils import TimeoutExpiredError, TimeoutSampler


LOGGER = logging.getLogger(__name__)


def _get_status_condition_log_message(**status_condition):
    log_msg = "Waiting For: \n"
    for status_condition_name, status_condition in status_condition.items():
        log_msg += (
            f"{status_condition_name}->{status_condition} \n"
            if status_condition
            else ""
        )

    return log_msg


class MTV:
    """
    Abstract Class for all Migration ToolKit For Virtualization (MTV) Resources.
    """

    def __init__(self):
        if self.__class__.__name__ == "MTV":
            raise TypeError("MTV is not a Resource.Please Use one of it's successors.")

    class StatusCondition:
        class Message:
            NETWORK_MAP_READY = "The network map is ready."

        class Status:
            TRUE = "True"

        class Type:
            READY = "Ready"

    def wait_for_resource_status(
        self,
        condition_status,
        condition_type,
        condition_message=None,
        condition_reason=None,
        condition_category=None,
        wait_timeout=600,
    ):
        """
        Waits for a MTV Resource status conditions.
        """

        LOGGER.info(
            _get_status_condition_log_message(
                condition_status=condition_status,
                condition_type=condition_type,
                condition_message=condition_message,
                condition_reason=condition_reason,
                condition_category=condition_category,
            )
        )

        samples = TimeoutSampler(
            wait_timeout=wait_timeout,
            sleep=1,
            func=self.api().get,
            field_selector=f"metadata.name=={self.name}",
            namespace=self.namespace,
        )
        last_condition = None
        try:
            for sample in samples:
                current_conditions = (
                    sample.items[0].status.get("conditions")
                    if sample.items and sample.items[0].status
                    else []
                )
                for condition in current_conditions:
                    last_condition = condition
                    if (
                        condition_status == condition.status
                        and condition_type == condition.type
                    ):
                        if (
                            condition_message == condition.message
                            or condition_status is None
                        ):
                            if (
                                condition.reason == condition.reason
                                or condition.reason is None
                            ):
                                if (
                                    condition_category == condition.category
                                    or condition_category is None
                                ):
                                    return

        except TimeoutExpiredError:
            LOGGER.error(
                msg=f"Last Status Conditions of {self.kind} {self.name} were: {last_condition}"
            )
            raise
