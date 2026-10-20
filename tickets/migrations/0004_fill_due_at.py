from datetime import timedelta

from django.db import migrations

SLA_HOURS = {"high": 4, "medium": 24, "low": 72}


def fill_due_at(apps, schema_editor):
    """Chamados antigos ganham prazo calculado a partir da data de criação."""
    Ticket = apps.get_model("tickets", "Ticket")
    for ticket in Ticket.objects.filter(due_at__isnull=True):
        ticket.due_at = ticket.created_at + timedelta(hours=SLA_HOURS[ticket.priority])
        ticket.save(update_fields=["due_at"])


class Migration(migrations.Migration):
    dependencies = [("tickets", "0003_sla_and_events")]

    operations = [migrations.RunPython(fill_due_at, migrations.RunPython.noop)]
