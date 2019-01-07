from django_import_data.models import audit_factory

from .models import Person

PersonAudit = audit_factory(Person)
