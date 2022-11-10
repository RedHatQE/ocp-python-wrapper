# -*- coding: utf-8 -*-

from ocp_resources.constants import PROTOCOL_ERROR_EXCEPTION_DICT, TIMEOUT_4MINUTES
from ocp_resources.logger import get_logger
from ocp_resources.resource import Resource
from ocp_resources.utils import TimeoutSampler


LOGGER = get_logger(name=__name__)


class CDIConfig(Resource):
    """
    CDIConfig object.
    """

    api_group = Resource.ApiGroup.CDI_KUBEVIRT_IO

    @property
    def scratch_space_storage_class_from_spec(self):
        return self.instance.spec.scratchSpaceStorageClass

    @property
    def scratch_space_storage_class_from_status(self):
        return self.instance.status.scratchSpaceStorageClass

    @property
    def upload_proxy_url(self):
        return self.instance.status.uploadProxyURL

    def wait_until_upload_url_changed(self, uploadproxy_url, timeout=TIMEOUT_4MINUTES):
        """
        Wait until upload proxy url is changed

        Args:
            timeout (int): Time to wait for CDI Config.

        Returns:
            bool: True if url is equal to uploadProxyURL.
        """
        LOGGER.info(
            f"Wait for {self.kind} {self.name} to ensure current URL == uploadProxyURL"
        )
        samples = TimeoutSampler(
            wait_timeout=timeout,
            sleep=1,
            exceptions_dict=PROTOCOL_ERROR_EXCEPTION_DICT,
            func=self.api.get,
            field_selector=f"metadata.name=={self.name}",
        )
        for sample in samples:
            if sample.items:
                status = sample.items[0].status
                current_url = status.uploadProxyURL
                if current_url == uploadproxy_url:
                    return

    @classmethod
    def is_garbage_collector_enabled_cdi_config(cls):
        """ Check if garbage collector enabled on config CDIconfig resource"""
        dv_ttl_seconds = cls(name="config").instance.spec.get("dataVolumeTTLSeconds")
        return dv_ttl_seconds is None or dv_ttl_seconds >= 0
