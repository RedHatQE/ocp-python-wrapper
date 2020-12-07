# -*- coding: utf-8 -*-

import logging

from .resource import NamespacedResource


LOGGER = logging.getLogger(__name__)


class UploadTokenRequest(NamespacedResource):
    """
    OpenShift UploadTokenRequest object.
    """

    api_group = NamespacedResource.ApiGroup.UPLOAD_CDI_KUBEVIRT_IO

    def __init__(self, name, namespace, pvc_name=None, teardown=True, client=None):
        super().__init__(
            name=name, namespace=namespace, client=client, teardown=teardown
        )
        self.pvc_name = pvc_name

    def to_dict(self):
        res = super()._base_body()
        res.update({"spec": {"pvcName": self.pvc_name}})
        return res
