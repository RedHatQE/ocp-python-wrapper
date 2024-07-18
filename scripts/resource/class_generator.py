from __future__ import annotations
import pprint

from typing import Any, Dict, List, Tuple
import click
import re

from jinja2 import DebugUndefined, Environment, FileSystemLoader, meta
from simple_logger.logger import get_logger

TYPE_MAPPING: Dict[str, str] = {
    "<integer>": "int",
    "<Object>": "Dict[Any, Any]",
    "<[]Object>": "List[Any]",
    "<string>": "str",
    "<map[string]string>": "Dict[Any, Any]",
    "<boolean>": "bool",
}
LOGGER = get_logger(name=__name__)


def format_resource_kind(resource_kind: str) -> str:
    """Convert CamelCase to snake_case"""
    return re.sub(r"(?<!^)(?<=[a-z])(?=[A-Z])", "_", resource_kind).lower().strip()


def name_and_type_from_field(field: str) -> Tuple[str, str, bool]:
    splited_field = field.split()
    _name, _type = splited_field[0], splited_field[1]

    name = format_resource_kind(resource_kind=_name)
    type_ = _type.strip()
    required = "-required-" in splited_field
    type_from_dict = TYPE_MAPPING.get(type_, "Dict[Any, Any]")

    # All non required fields must be set with Optional
    if not required:
        if type_from_dict == "Dict[Any, Any]":
            type_from_dict = "Option[Dict[str, Any]] = None"

        if type_from_dict == "List[Any]":
            type_from_dict = "Option[List[Any]] = None"

        if type_from_dict == "str":
            type_from_dict = "Option[str] = ''"

        if type_from_dict == "bool":
            type_from_dict = "Option[bool] = None"

        if type_from_dict == "int":
            type_from_dict = "Option[int] = None"

    return name, f"{name}: {type_from_dict}", required


def generate_resource_file_from_dict(resource_dict: Dict[str, Any]) -> None:
    env = Environment(
        loader=FileSystemLoader("manifests"),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=DebugUndefined,
    )

    template = env.get_template(name="class_generator_template.j2")
    rendered = template.render(resource_dict)
    undefined_variables = meta.find_undeclared_variables(env.parse(rendered))
    if undefined_variables:
        LOGGER.error(f"The following variables are undefined: {undefined_variables}")
        raise click.Abort()

    with open(f"ocp_resources/{format_resource_kind(resource_kind=resource_dict['KIND'])}.py_", "w") as fd:
        fd.write(rendered)


def resource_from_explain_file(file: str, namespaced: bool, api_link: str) -> Dict[str, Any]:
    section_data: str = ""
    sections: List[str] = []
    resource_dict: Dict[str, Any] = {
        "BASE_CLASS": "NamespacedResource" if namespaced else "Resource",
        "API_LINK": api_link,
    }
    new_sections_words: Tuple[str, str, str] = ("KIND:", "VERSION:", "GROUP:")

    with open(file) as fd:
        data = fd.read()

    for line in data.splitlines():
        # If line is empty section is done
        if not line.strip():
            if section_data:
                sections.append(section_data)
                section_data = ""

            continue

        section_data += f"{line}\n"
        if line.startswith(new_sections_words):
            if section_data:
                sections.append(section_data)
                section_data = ""
            continue

    # Last section data from last iteration
    if section_data:
        sections.append(section_data)

    start_fields_section: str = ""

    for section in sections:
        if section.startswith("FIELDS:"):
            start_fields_section = section
            continue

        key, val = section.split(":")
        resource_dict[key.strip()] = val.strip()

    resource_dict["SPEC"] = []
    first_field_indent: int = 0
    first_field_indent_str: str = ""
    top_spec_indent_str: str = ""
    first_field_spec_found: bool = False
    field_spec_found: bool = False

    for field in start_fields_section.splitlines():
        if field.startswith("FIELDS:"):
            continue

        # Find first indent of spec, Needed in order to now when spec is done.
        if not first_field_indent:
            first_field_indent = len(re.findall(r" +", field)[0])
            first_field_indent_str = f"{' ' * first_field_indent}"
            continue

        if field.startswith(f"{first_field_indent_str}spec"):
            first_field_spec_found = True
            field_spec_found = True
            continue

        if field_spec_found:
            if not re.findall(rf"^{first_field_indent_str}\w", field):
                if first_field_spec_found:
                    resource_dict["SPEC"].append(name_and_type_from_field(field=field))

                    # Get top level keys inside spec indent, need to match only once.
                    top_spec_indent = len(re.findall(r" +", field)[0])
                    top_spec_indent_str = f"{' ' * top_spec_indent}"
                    first_field_spec_found = False
                    continue

                if top_spec_indent_str:
                    # Get only top level keys from inside spec
                    if re.findall(rf"^{top_spec_indent_str}\w", field):
                        resource_dict["SPEC"].append(name_and_type_from_field(field=field))
                        continue

            else:
                break

    resource_dict["SPEC"].sort(key=lambda x: not x[-1])
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(object=resource_dict)
    return resource_dict


def validate_api_link_schema(ctx: click.Context, param: click.Option | click.Parameter, value: Any) -> Any:
    if not value.startswith("https://"):
        raise click.BadParameter("Resource API linkn must start with https://")

    return value


@click.command("Resource class generator")
@click.option(
    "-f",
    "--file",
    type=click.Path(exists=True),
    help="File containing the content of: `oc explain <KIND> --recursive`",
)
@click.option(
    "-ns",
    "--namespaced",
    is_flag=True,
    help="""
    \b
    Indicate if the resource is nemaspaced or not.
        Get it by:  `oc api-resources --namespaced | grep <KIND>`
    """,
)
@click.option(
    "-l",
    "--api-link",
    required=True,
    type=click.UNPROCESSED,
    callback=validate_api_link_schema,
    help="A link to the resource doc/api in the web",
)
def main(file, namespaced, api_link):
    resource_dict = resource_from_explain_file(file=file, namespaced=namespaced, api_link=api_link)
    generate_resource_file_from_dict(resource_dict=resource_dict)


if __name__ == "__main__":
    main()
