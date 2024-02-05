# API reference: https://github.com/kubevirt/application-aware-quota/blob/main/README.md
# TODO: update API reference when OCP doc is available
# TODO: Add missing code e.g. to_dict()

from ocp_resources.resource import Resource


class AAQ(Resource):
    """
    AAQ object.
    """

    api_group = Resource.ApiGroup.AAQ_KUBEVIRT_IO
