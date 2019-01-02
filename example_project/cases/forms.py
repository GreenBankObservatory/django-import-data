from django import forms

from .models import Structure, Person, Case


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ("name", "phone", "email")


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ("case_num", "applicant")


class StructureForm(forms.ModelForm):
    class Meta:
        model = Structure
        fields = ("location",)
