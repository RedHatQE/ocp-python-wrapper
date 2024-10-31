import json
from typing import List, Any, Dict

from ocp_resources.resource import NamespacedResource


class ClusterServiceVersion(NamespacedResource):
    api_group = NamespacedResource.ApiGroup.OPERATORS_COREOS_COM

    class Status(NamespacedResource.Status):
        INSTALLING = "Installing"

    def get_alm_examples(self) -> List[Dict[str, Any]]:
        """
        Parse the alm-examples annotation from the CSV instance and return a list of dictionaries.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries from alm-examples.

        Raises:
            json.JSONDecodeError: If the alm-examples annotation is not valid JSON.
            ValueError: If no alm-examples annotation is found.
        """

        examples = self.instance.metadata.annotations.get("alm-examples", "[]")
        try:
            if not examples:
                self.logger.debug("No alm-examples annotation found in CSV")
                raise ValueError("No alm-examples annotation found")
            return json.loads(examples)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse alm-examples annotation: {e}")
            raise
