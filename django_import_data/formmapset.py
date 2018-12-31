from collections import OrderedDict


def _flatten_dependencies(dependencies):
    flat = OrderedDict()

    if isinstance(dependencies, dict):
        for key, value in dependencies.items():
            flat[key] = list(value)
            flat.update(_flatten_dependencies(value))
    else:
        flat.update({d: [] for d in dependencies})

    return flat


def flatten_dependencies(dependencies):
    flat = _flatten_dependencies(dependencies)
    return OrderedDict(reversed(flat.items()))


class FormMapSet:
    def __init__(self, form_maps, dependencies=None):
        self.form_maps = form_maps
        if dependencies is None:
            self.dependencies = {}
        else:
            self.dependencies = dependencies

    # TODO: Need to detect unprocessed still
    def render(self, data, allow_unprocessed=False):
        flat = flatten_dependencies(self.dependencies)
        print(f"FLAT: {flat}")
        rendered = {}

        for field, deps in flat.items():
            extra = {dep: rendered[dep].id for dep in deps}
            print(f"Saving {self.form_maps[field]} with extra: {extra}")

            rendered[field] = self.form_maps[field].save(data, extra=extra)

        return rendered

    def report(self):
        print(f"Yo wut up: {self.form_maps}")
