# Restrcuture the data input from Excel sheet

import json
from jinja2 import Environment, Template, FileSystemLoader


def render_jinja(template_name=None, data=None, folder=None, template_content=None):
    """
    Renders a Jinja2 template.

    - If `template_content` is provided, use it as the template.
    - Otherwise, load the template from a file (requires `template_name` and `folder`).

    Args:
    - template_name (str): Name of the Jinja2 template file (only used if `template_content` is None).
    - data (dict): Data to render the template with.
    - folder (str): Folder where the template files are stored (used when loading from file).
    - template_content (str): Raw template content (used when not loading from file).

    Returns:
    - Rendered string.
    """
    if template_content:
        # Render from provided template content (from Excel or other sources)
        template = Template(template_content)
    else:
        # Load template from file system
        env = Environment(
            lstrip_blocks=True,
            loader=FileSystemLoader(f'jinja_templates/{folder}')
        )
        template = env.get_template(template_name)

    # Render the template with the provided data
    return template.render(data)

def to_json(rendered_jinja):
    return json.loads(rendered_jinja)