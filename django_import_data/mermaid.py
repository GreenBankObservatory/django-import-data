import uuid

from django.template.loader import render_to_string


def render_field_map_as_mermaid(field_map, orientation="LR", include_subgraphs=True):
    context = {"field_map": field_map, "include_subgraphs": include_subgraphs}
    if orientation:
        context["graph_type"] = f"graph {orientation}"
    return render_to_string("field_map_as_mermaid.html", context)


def render_form_map_as_mermaid(
    form_map, orientation="LR", layout="columns", include_subgraphs=True
):
    context = {
        "form_map": form_map,
        "uuid": lambda: uuid.uuid4().hex,
        "include_subgraphs": include_subgraphs,
    }
    if orientation:
        context["graph_type"] = f"graph {orientation}"
    if layout == "columns":
        return render_to_string("form_map_as_mermaid.html", context)
    elif layout == "rows":
        return render_to_string("form_map_as_mermaid.html", context)
    else:
        raise ValueError(
            f"Invalid layout given: {layout}. Should be either 'rows' or 'columns'"
        )
