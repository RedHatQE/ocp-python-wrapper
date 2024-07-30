from __future__ import annotations
import json
import shlex
import os
import sys
from pathlib import Path

from typing import Any, Dict, List, Optional, Tuple
import click
import re

import cloup
from cloup.constraints import If, accept_none, mutually_exclusive, require_any
from pyhelper_utils.shell import run_command
from rich.console import Console

from rich.prompt import Prompt
from ocp_resources.resource import Resource

from jinja2 import DebugUndefined, Environment, FileSystemLoader, meta
from simple_logger.logger import get_logger
from pyhelper_utils.runners import function_runner_with_pdb


SPEC_STR: str = "SPEC"
FIELDS_STR: str = "FIELDS"

TYPE_MAPPING: Dict[str, str] = {
    "<integer>": "int",
    "<Object>": "Dict[Any, Any]",
    "<[]Object>": "List[Any]",
    "<string>": "str",
    "<map[string]string>": "Dict[Any, Any]",
    "<boolean>": "bool",
}
LOGGER = get_logger(name="class_generator")
TESTS_MANIFESTS_DIR = "scripts/resource/tests/manifests"


def get_oc_or_kubectl() -> str:
    if run_command(command=shlex.split("which oc"), check=False)[0]:
        return "oc"

    elif run_command(command=shlex.split("which kubectl"), check=False)[0]:
        return "kubectl"

    else:
        LOGGER.error("oc or kubectl not available")
        sys.exit(1)


def check_cluster_available() -> bool:
    _exec = get_oc_or_kubectl()
    if not _exec:
        return False

    return run_command(command=shlex.split(f"{_exec} version"), check=False)[0]


def write_to_file(data: Dict[str, Any], output_debug_file_path: str) -> None:
    content = {}
    if os.path.isfile(output_debug_file_path):
        with open(output_debug_file_path) as fd:
            content = json.load(fd)

    content.update(data)

    Path(output_debug_file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_debug_file_path, "w") as fd:
        json.dump(content, fd, indent=4)


def get_kind_data_and_debug_file(kind: str, debug: bool = False, add_tests: bool = False) -> Dict[str, Any]:
    """
    Get oc/kubectl explain output for given kind, if kind is namespaced and debug filepath
    """
    _, explain_out, _ = run_command(command=shlex.split(f"oc explain {kind} --recursive"))

    resource_kind = re.search(r".*?KIND:\s+(.*?)\n", explain_out)
    resource_kind_str: str = ""

    if resource_kind:
        resource_kind_str = resource_kind.group(1)  # noqa FCN001
        formatted_kind_name = convert_camel_case_to_snake_case(string_=resource_kind_str)
    else:
        formatted_kind_name = convert_camel_case_to_snake_case(string_=kind)

    output_debug_file_path: str = ""
    if debug or add_tests:
        output_debug_dir = (
            os.path.join(TESTS_MANIFESTS_DIR, formatted_kind_name)
            if add_tests
            else os.path.join(os.path.dirname(__file__), "debug")
        )
        output_debug_file_path = os.path.join(output_debug_dir, f"{formatted_kind_name}_debug.json")

    if output_debug_file_path:
        write_to_file(
            data={"explain": explain_out},
            output_debug_file_path=output_debug_file_path,
        )

    if not resource_kind:
        LOGGER.error(f"Failed to get resource kind from explain for {kind}")
        return {}

    _, namespace_out, _ = run_command(
        command=shlex.split(f"bash -c 'oc api-resources --namespaced | grep -w {resource_kind_str} | wc -l'"),
        check=False,
    )
    if output_debug_file_path:
        write_to_file(
            data={"namespace": namespace_out},
            output_debug_file_path=output_debug_file_path,
        )

    return {
        "data": explain_out,
        "namespaced": namespace_out.strip() == "1",
        "debug_file": output_debug_file_path,
    }


def convert_camel_case_to_snake_case(string_: str) -> str:
    """
    Converts a camel case string to snake case.

    Args:
        string_ (str): The camel case string to convert.

    Returns:
        str: The snake case representation of the input string.

    Examples:
        >>> convert_camel_case_to_snake_case(string_="allocateLoadBalancerNodePorts")
        'allocate_load_balancer_node_ports'
        >>> convert_camel_case_to_snake_case(string_="clusterIPs")
        'cluster_ips'
        >>> convert_camel_case_to_snake_case(string_="additionalCORSAllowedOS")
        'additional_cors_allowed_os'

    Notes:
        - This function assumes that the input string adheres to camel case conventions.
        - If the input string contains acronyms (e.g., "XMLHttpRequest"), they will be treated as separate words
          (e.g., "xml_http_request").
        - The function handles both single-word camel case strings (e.g., "Service") and multi-word camel case strings
          (e.g., "myCamelCaseString").
    """
    formatted_str: str = ""

    if string_.islower():
        return string_

    # For single words, e.g "Service" or "SERVICE"
    if string_.istitle() or string_.isupper():
        return string_.lower()

    # To decide if underscore is needed before a char, keep the last char format.
    # If previous char is uppercase, underscode should not be added. Also applied for the first char in the string.
    last_capital_char: bool | None = None

    # To decide if there are additional words ahead; if found, there is at least one more word ahead, else this is the
    # last word. Underscore should be added before it and all chars from here should be lowercase.
    following_capital_chars: re.Match | None = None

    str_len_for_idx_check = len(string_) - 1

    for idx, char in enumerate(string_):
        # If lower case, append to formatted string
        if char.islower():
            formatted_str += char
            last_capital_char = False

        # If first char is uppercase
        elif idx == 0:
            formatted_str += char.lower()
            last_capital_char = True

        else:
            if idx < str_len_for_idx_check:
                following_capital_chars = re.search(r"[A-Z]", "".join(string_[idx + 1 :]))
            if last_capital_char:
                if idx < str_len_for_idx_check and string_[idx + 1].islower():
                    if following_capital_chars:
                        formatted_str += f"_{char.lower()}"
                        last_capital_char = True
                        continue

                    remaining_str = "".join(string_[idx:])
                    # The 2 letters in the string; uppercase char followed by lowercase char.
                    # Example: `clusterIPs`, handle `Ps` at this point
                    if idx + 1 == str_len_for_idx_check:
                        formatted_str += remaining_str.lower()
                        break

                    # The last word in the string; uppercase followed by multiple lowercase chars
                    # Example: `dataVolumeTTLSeconds`, handle `Seconds` at this point
                    elif remaining_str.istitle():
                        formatted_str += f"_{remaining_str.lower()}"
                        break

                    else:
                        formatted_str += char.lower()
                        last_capital_char = True

                else:
                    formatted_str += char.lower()
                    last_capital_char = True

            else:
                formatted_str += f"_{char.lower()}"
                last_capital_char = True

    return formatted_str


def get_field_description(
    kind: str,
    field_name: str,
    field_under_spec: bool,
    debug: bool,
    output_debug_file_path: str = "",
    debug_content: Optional[Dict[str, str]] = None,
    add_tests: bool = False,
) -> str:
    if debug_content:
        _out = debug_content[f"explain-{field_name}"]

    else:
        _, _out, _ = run_command(
            command=shlex.split(f"oc explain {kind}{'.spec' if field_under_spec else ''}.{field_name}"),
            check=False,
            verify_stderr=False,
        )

    if debug or add_tests:
        write_to_file(
            data={f"explain-{field_name}": _out},
            output_debug_file_path=output_debug_file_path,
        )

    _description = re.search(r"DESCRIPTION:\n\s*(.*)", _out, re.DOTALL)
    if _description:
        description: str = ""
        _fields_found = False
        for line in _description.group(1).strip().splitlines():
            if line.strip():
                if line.startswith("FIELDS:"):
                    _fields_found = True
                    description += f"{' ' * 4}{line}\n"
                else:
                    indent = 4 if _fields_found else 0
                    description += f"{' ' * indent}{line}\n"
            else:
                indent = 8 if _fields_found else 4
                description += f"{' ' * indent}{line}\n"

        return f"{description}\n"

    return "<please add description>"


def get_arg_params(
    field: str,
    kind: str,
    field_under_spec: bool = False,
    debug: bool = False,
    output_debug_file_path: str = "",
    debug_content: Optional[Dict[str, str]] = None,
    add_tests: bool = False,
) -> Dict[str, Any]:
    splited_field = field.split()
    _orig_name, _type = splited_field[0], splited_field[1]

    name = convert_camel_case_to_snake_case(string_=_orig_name)
    type_ = _type.strip()
    required: bool = "-required-" in splited_field
    type_from_dict: str = TYPE_MAPPING.get(type_, "Dict[Any, Any]")
    type_from_dict_for_init = type_from_dict

    # All fields must be set with Optional since resource can have yaml_file to cover all args.
    if type_from_dict == "Dict[Any, Any]":
        type_from_dict_for_init = "Optional[Dict[str, Any]] = None"

    if type_from_dict == "List[Any]":
        type_from_dict_for_init = "Optional[List[Any]] = None"

    if type_from_dict == "str":
        type_from_dict_for_init = 'Optional[str] = ""'

    if type_from_dict == "bool":
        type_from_dict_for_init = "Optional[bool] = None"

    if type_from_dict == "int":
        type_from_dict_for_init = "Optional[int] = None"

    _res: Dict[str, Any] = {
        "name-from-explain": _orig_name,
        "name-for-class-arg": name,
        "type-for-class-arg": f"{name}: {type_from_dict_for_init}",
        "required": required,
        "type": type_from_dict,
        "description": get_field_description(
            kind=kind,
            field_name=_orig_name,
            field_under_spec=field_under_spec,
            debug=debug,
            output_debug_file_path=output_debug_file_path,
            debug_content=debug_content,
            add_tests=add_tests,
        ),
    }

    return _res


def render_jinja_template(template_dict: Dict[Any, Any], template_dir: str, template_name: str):
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=DebugUndefined,
    )

    template = env.get_template(name=template_name)
    rendered = template.render(template_dict)
    undefined_variables = meta.find_undeclared_variables(env.parse(rendered))

    if undefined_variables:
        LOGGER.error(f"The following variables are undefined: {undefined_variables}")
        sys.exit(1)

    return rendered


def generate_resource_file_from_dict(
    resource_dict: Dict[str, Any],
    overwrite: bool = False,
    dry_run: bool = False,
    output_file: str = "",
    interactive: bool = False,
    add_tests: bool = False,
) -> str:
    rendered = render_jinja_template(
        template_dict=resource_dict,
        template_dir="scripts/resource/manifests",
        template_name="class_generator_template.j2",
    )

    temp_output_file: str = ""

    formatted_kind_str = convert_camel_case_to_snake_case(string_=resource_dict["KIND"])
    if add_tests:
        overwrite = True
        _output_file = os.path.join(TESTS_MANIFESTS_DIR, formatted_kind_str, f"{formatted_kind_str}_res.py")
    elif output_file:
        _output_file = output_file
    else:
        _output_file = os.path.join("ocp_resources", f"{formatted_kind_str}.py")

    if os.path.exists(_output_file):
        if overwrite:
            LOGGER.warning(f"Overwriting {_output_file}")

        elif interactive:
            if Prompt.ask(prompt=f"Overwrite {_output_file}?", choices=["y", "n"]) == "n":
                if user_file_name := Prompt.ask(prompt="Provide file name"):
                    _output_file = user_file_name
                else:
                    LOGGER.error("No file name provided")
                    sys.exit(1)

        else:
            temp_output_file = f"{_output_file[:-3]}_TEMP.py"
            LOGGER.warning(f"{_output_file} already exists, using {temp_output_file}")
            _output_file = temp_output_file

    if dry_run:
        Console().print(rendered)

    else:
        write_and_format_rendered(filepath=_output_file, data=rendered)

    return _output_file


def parse_explain(
    output: str,
    namespaced: Optional[bool] = None,
    debug: bool = False,
    output_debug_file_path: str = "",
    debug_content: Optional[Dict[str, str]] = None,
    add_tests: bool = False,
) -> Dict[str, Any]:
    section_data: str = ""
    sections: List[str] = []
    resource_dict: Dict[str, Any] = {
        "BASE_CLASS": "NamespacedResource" if namespaced else "Resource",
    }
    new_sections_words: Tuple[str, str, str] = ("KIND:", "VERSION:", "GROUP:")

    for line in output.splitlines():
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
        if section.startswith(f"{FIELDS_STR}:"):
            start_fields_section = section
            continue

        key, val = section.split(":", 1)
        resource_dict[key.strip()] = val.strip()

    kind = resource_dict["KIND"]
    keys_to_ignore = ["metadata", "kind", "apiVersion", "status"]
    resource_dict[SPEC_STR] = []
    resource_dict[FIELDS_STR] = []
    first_field_indent: int = 0
    first_field_indent_str: str = ""
    top_spec_indent: int = 0
    top_spec_indent_str: str = ""
    first_field_spec_found: bool = False
    field_spec_found: bool = False

    for field in start_fields_section.splitlines():
        if field.startswith(f"{FIELDS_STR}:"):
            continue

        start_spec_field = field.startswith(f"{first_field_indent_str}{SPEC_STR.lower()}")
        ignored_field = field.split()[0] in keys_to_ignore
        # Find first indent of spec, Needed in order to now when spec is done.
        if not first_field_indent:
            first_field_indent = len(re.findall(r" +", field)[0])
            first_field_indent_str = f"{' ' * first_field_indent}"
            if not ignored_field and not start_spec_field:
                resource_dict[FIELDS_STR].append(
                    get_arg_params(
                        field=field,
                        kind=kind,
                        debug=debug,
                        debug_content=debug_content,
                        output_debug_file_path=output_debug_file_path,
                        add_tests=add_tests,
                    )
                )

            continue
        else:
            if len(re.findall(r" +", field)[0]) == len(first_field_indent_str):
                if not ignored_field and not start_spec_field:
                    resource_dict[FIELDS_STR].append(
                        get_arg_params(
                            field=field,
                            kind=kind,
                            debug=debug,
                            debug_content=debug_content,
                            output_debug_file_path=output_debug_file_path,
                            add_tests=add_tests,
                        )
                    )

        if start_spec_field:
            first_field_spec_found = True
            field_spec_found = True
            continue

        if field_spec_found:
            if not re.findall(rf"^{first_field_indent_str}\w", field):
                if first_field_spec_found:
                    resource_dict[SPEC_STR].append(
                        get_arg_params(
                            field=field,
                            kind=kind,
                            field_under_spec=True,
                            debug=debug,
                            debug_content=debug_content,
                            output_debug_file_path=output_debug_file_path,
                            add_tests=add_tests,
                        )
                    )

                    # Get top level keys inside spec indent, need to match only once.
                    top_spec_indent = len(re.findall(r" +", field)[0])
                    top_spec_indent_str = f"{' ' * top_spec_indent}"
                    first_field_spec_found = False
                    continue

                if top_spec_indent_str:
                    # Get only top level keys from inside spec
                    if re.findall(rf"^{top_spec_indent_str}\w", field):
                        resource_dict[SPEC_STR].append(
                            get_arg_params(
                                field=field,
                                kind=kind,
                                field_under_spec=True,
                                debug=debug,
                                debug_content=debug_content,
                                output_debug_file_path=output_debug_file_path,
                                add_tests=add_tests,
                            )
                        )
                        continue

            else:
                break

    if not resource_dict[SPEC_STR] and not resource_dict[FIELDS_STR]:
        LOGGER.error(f"Unable to parse {kind} resource.")
        return {}

    api_group_real_name = resource_dict.get("GROUP")
    # If API Group is not present in resource, try to get it from VERSION
    if not api_group_real_name:
        version_splited = resource_dict["VERSION"].split("/")
        if len(version_splited) == 2:
            api_group_real_name = version_splited[0]

    if api_group_real_name:
        api_group_for_resource_api_group = api_group_real_name.upper().replace(".", "_")
        resource_dict["GROUP"] = api_group_for_resource_api_group
        missing_api_group_in_resource: bool = not hasattr(Resource.ApiGroup, api_group_for_resource_api_group)

        if missing_api_group_in_resource:
            LOGGER.warning(
                f"Missing API Group in Resource\n"
                f"Please add `Resource.ApiGroup.{api_group_for_resource_api_group} = {api_group_real_name}` "
                "manually into ocp_resources/resource.py under Resource class > ApiGroup class."
            )

    else:
        api_version_for_resource_api_version = resource_dict["VERSION"].upper()
        missing_api_version_in_resource: bool = not hasattr(Resource.ApiVersion, api_version_for_resource_api_version)

        if missing_api_version_in_resource:
            LOGGER.warning(
                f"Missing API Version in Resource\n"
                f"Please add `Resource.ApiVersion.{api_version_for_resource_api_version} = {resource_dict['VERSION']}` "
                "manually into ocp_resources/resource.py under Resource class > ApiGroup class."
            )

    return resource_dict


def check_kind_exists(kind: str) -> bool:
    return run_command(
        command=shlex.split(f"oc explain {kind}"),
        check=False,
    )[0]


def get_user_args_from_interactive() -> str:
    kind = Prompt.ask(prompt="Enter the resource kind to generate class for")
    if not kind:
        return ""

    return kind


def class_generator(
    kind: str = "",
    overwrite: bool = False,
    interactive: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    process_debug_file: str = "",
    output_file: str = "",
    add_tests: bool = False,
) -> str:
    """
    Generates a class for a given Kind.
    """
    debug_content: Dict[str, str] = {}

    if process_debug_file:
        debug = False
        with open(process_debug_file) as fd:
            debug_content = json.load(fd)

        kind_data: Dict[str, Any] = {
            "data": debug_content["explain"],
            "namespaced": debug_content["namespace"].strip() == "1",
        }

    else:
        if not check_cluster_available():
            LOGGER.error(
                "Cluster not available, The script needs a running cluster and admin privileges to get the explain output"
            )
            sys.exit(1)

        if interactive:
            kind = get_user_args_from_interactive()

        if not kind:
            LOGGER.error("Kind or API link not provided")
            sys.exit(1)

        if not check_kind_exists(kind=kind):
            sys.exit(1)

        kind_data = get_kind_data_and_debug_file(
            kind=kind,
            debug=debug,
            add_tests=add_tests,
        )
        if not kind_data:
            sys.exit(1)

    output_debug_file_path = kind_data.get("debug_file", "")

    resource_dict = parse_explain(
        output=kind_data["data"],
        namespaced=kind_data["namespaced"],
        debug=debug,
        output_debug_file_path=output_debug_file_path,
        debug_content=debug_content,
        add_tests=add_tests,
    )
    if not resource_dict:
        return ""

    generated_py_file = generate_resource_file_from_dict(
        resource_dict=resource_dict,
        overwrite=overwrite,
        dry_run=dry_run,
        output_file=output_file,
        interactive=interactive,
        add_tests=add_tests,
    )

    if not dry_run:
        run_command(
            command=shlex.split(f"pre-commit run --files {generated_py_file}"),
            verify_stderr=False,
            check=False,
        )

    if debug or add_tests:
        LOGGER.info(f"Debug output saved to {output_debug_file_path}")

    return generated_py_file


def write_and_format_rendered(filepath, data):
    with open(filepath, "w") as fd:
        fd.write(data)

    for op in ("format", "check"):
        run_command(
            command=shlex.split(f"poetry run ruff {op} {filepath}"),
            verify_stderr=False,
            check=False,
        )


def generate_class_generator_tests():
    tests_info: Dict[str, List[Dict[str, str]]] = {"template": []}

    for _dir in os.listdir(TESTS_MANIFESTS_DIR):
        dir_path = os.path.join(TESTS_MANIFESTS_DIR, _dir)
        if os.path.isdir(dir_path):
            test_data = {"kind": _dir}

            for _file in os.listdir(dir_path):
                if _file.endswith("_debug.json"):
                    test_data["debug_file"] = _file
                elif _file.endswith("_res.py"):
                    test_data["res_file"] = _file

            tests_info["template"].append(test_data)

    rendered = render_jinja_template(
        template_dict=tests_info,
        template_dir=TESTS_MANIFESTS_DIR,
        template_name="test_parse_explain.j2",
    )

    write_and_format_rendered(
        filepath=os.path.join(Path(TESTS_MANIFESTS_DIR).parent, "test_class_generator.py"),
        data=rendered,
    )


@cloup.command("Resource class generator")
@cloup.option("-i", "--interactive", is_flag=True, help="Enable interactive mode")
@cloup.option(
    "-k",
    "--kind",
    type=click.STRING,
    help="The Kind to generate the class for, Needs working cluster with admin privileges",
)
@cloup.option(
    "-o",
    "--output-file",
    help="The full filename path to generate a python resource file. If not sent, resource kind will be used",
    type=click.Path(),
)
@cloup.option(
    "--overwrite",
    is_flag=True,
    help="Output file overwrite existing file if passed",
)
@cloup.option("--dry-run", is_flag=True, help="Run the script without writing to file")
@cloup.option("-d", "--debug", is_flag=True, help="Save all command output to debug file")
@cloup.option(
    "--debug-file",
    type=click.Path(exists=True),
    help="Run the script from debug file. (generated by --debug)",
)
@cloup.option(
    "--pdb",
    help="Drop to `ipdb` shell on exception",
    is_flag=True,
    show_default=True,
)
@cloup.option(
    "--add-tests",
    help=f"Add a test to `test_class_generator.py` and test files to `{TESTS_MANIFESTS_DIR}` dir",
    is_flag=True,
    show_default=True,
)
@cloup.constraint(mutually_exclusive, ["add_tests", "debug"])
@cloup.constraint(mutually_exclusive, ["add_tests", "output_file"])
@cloup.constraint(mutually_exclusive, ["add_tests", "dry_run"])
@cloup.constraint(mutually_exclusive, ["interactive", "kind"])
@cloup.constraint(If("debug_file", then=accept_none), ["interactive", "kind"])
@cloup.constraint(require_any, ["interactive", "kind"])
def main(
    kind: str,
    overwrite: bool,
    interactive: bool,
    dry_run: bool,
    debug: bool,
    debug_file: str,
    output_file: str,
    pdb: bool,
    add_tests: bool,
):
    _ = pdb

    class_generator(
        kind=kind,
        overwrite=overwrite,
        interactive=interactive,
        dry_run=dry_run,
        debug=debug,
        process_debug_file=debug_file,
        output_file=output_file,
        add_tests=add_tests,
    )

    if add_tests:
        generate_class_generator_tests()


if __name__ == "__main__":
    function_runner_with_pdb(func=main)
