from django import forms

from .models import Person, Attachment, Case, CaseGroup


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ("name", "phone", "email")


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ("path",)


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ("applicant", "attachments", "group")


class CaseGroupForm(forms.ModelForm):
    class Meta:
        model = CaseGroup
        fields = ("name",)
