from django import forms
from django.contrib.auth import get_user_model

from tickets.models import Comment, Ticket
from tickets.permissions import agents_queryset


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "category", "priority", "description"]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body", "internal"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, can_be_internal=False, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        if not can_be_internal:
            del self.fields["internal"]


class ManageForm(forms.ModelForm):
    """Só atendentes usam: muda status, prioridade e responsável."""

    class Meta:
        model = Ticket
        fields = ["status", "priority", "assignee"]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = agents_queryset()

    def clean_status(self):
        new_status = self.cleaned_data["status"]
        # neste ponto self.instance ainda tem o status antigo
        if not self.instance.can_change_to(new_status):
            raise forms.ValidationError(
                f"Não é possível ir de '{self.instance.get_status_display()}' "
                f"para '{dict(Ticket.Status.choices)[new_status]}'."
            )
        return new_status

    def describe_changes(self):
        """Frases para o histórico, uma por campo alterado."""
        names = {"status": "Status", "priority": "Prioridade", "assignee": "Responsável"}
        labels = {
            "status": dict(Ticket.Status.choices),
            "priority": dict(Ticket.Priority.choices),
        }
        lines = []
        for field in self.changed_data:
            old, new = self.initial.get(field), self.cleaned_data[field]
            if field == "assignee":
                old = get_user_model().objects.filter(pk=old).first() or "ninguém"
                new = new or "ninguém"
            else:
                old, new = labels[field][old], labels[field][new]
            lines.append(f"{names[field]} alterado de {old} para {new}")
        return lines
