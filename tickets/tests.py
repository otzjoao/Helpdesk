from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tickets.models import Category, Comment, Ticket

User = get_user_model()


class TicketTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.first()  # criada pela migration 0002
        cls.ana = User.objects.create_user("ana", "ana@x.com", "senha12345")
        cls.bia = User.objects.create_user("bia", "bia@x.com", "senha12345")
        cls.agent = User.objects.create_user("carlos", "c@x.com", "senha12345")
        cls.agent.groups.add(Group.objects.get(name="Atendentes"))
        cls.ticket = Ticket.objects.create(
            title="Sem internet", description="Cabo solto", category=cls.category,
            requester=cls.ana,
        )

    def test_anonymous_goes_to_login(self):
        response = self.client.get(reverse("tickets:list"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

    def test_requester_sees_only_own_tickets(self):
        Ticket.objects.create(
            title="Impressora", description="x", category=self.category, requester=self.bia
        )
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, "Sem internet")
        self.assertNotContains(response, "Impressora")

    def test_requester_cannot_open_other_ticket(self):
        self.client.force_login(self.bia)
        response = self.client.get(reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 404)

    def test_agent_sees_everything(self):
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 200)

    def test_create_ticket_sets_requester_and_sends_email(self):
        self.client.force_login(self.ana)
        response = self.client.post(reverse("tickets:create"), {
            "title": "Erro no sistema", "category": self.category.pk,
            "priority": "high", "description": "Tela branca",
        })
        ticket = Ticket.objects.get(title="Erro no sistema")
        self.assertRedirects(response, reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(ticket.requester, self.ana)
        self.assertEqual(len(mail.outbox), 1)

    def test_internal_comment_hidden_from_requester(self):
        Comment.objects.create(
            ticket=self.ticket, author=self.agent, body="segredo da equipe", internal=True
        )
        Comment.objects.create(
            ticket=self.ticket, author=self.agent, body="mensagem publica"
        )
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertContains(response, "mensagem publica")
        self.assertNotContains(response, "segredo da equipe")

    def test_requester_cannot_post_internal_comment(self):
        self.client.force_login(self.ana)
        self.client.post(
            reverse("tickets:comment", args=[self.ticket.pk]),
            {"body": "oi", "internal": "on"},
        )
        self.assertFalse(Comment.objects.get(body="oi").internal)

    def test_agent_reply_emails_requester(self):
        self.client.force_login(self.agent)
        self.client.post(
            reverse("tickets:comment", args=[self.ticket.pk]),
            {"body": "Verifique o cabo"},
        )
        self.assertEqual(mail.outbox[-1].to, ["ana@x.com"])

    def test_requester_cannot_manage_ticket(self):
        self.client.force_login(self.ana)
        response = self.client.post(
            reverse("tickets:manage", args=[self.ticket.pk]),
            {"status": "closed", "priority": "low"},
        )
        self.assertEqual(response.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")

    def test_assign_to_me_moves_to_in_progress(self):
        self.client.force_login(self.agent)
        self.client.post(reverse("tickets:assign", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assignee, self.agent)
        self.assertEqual(self.ticket.status, "in_progress")

    def test_valid_and_invalid_transitions(self):
        self.client.force_login(self.agent)
        url = reverse("tickets:manage", args=[self.ticket.pk])
        # open -> resolved nao e permitido
        self.client.post(url, {"status": "resolved", "priority": "medium"})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")
        # open -> in_progress e permitido
        self.client.post(url, {"status": "in_progress", "priority": "medium"})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")

    def test_closed_ticket_is_final(self):
        self.ticket.status = "closed"
        self.ticket.save()
        self.assertFalse(self.ticket.can_change_to("open"))

    def test_status_filter(self):
        Ticket.objects.create(
            title="Resolvido ja", description="x", category=self.category,
            requester=self.ana, status="resolved",
        )
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:list") + "?status=resolved")
        self.assertContains(response, "Resolvido ja")
        self.assertNotContains(response, "Sem internet")


class SlaDashboardHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.first()
        cls.ana = User.objects.create_user("ana", "ana@x.com", "senha12345")
        cls.agent = User.objects.create_user("carlos", "c@x.com", "senha12345")
        cls.agent.groups.add(Group.objects.get(name="Atendentes"))

    def make_ticket(self, **kwargs):
        data = dict(
            title="Chamado", description="x", category=self.category, requester=self.ana
        )
        data.update(kwargs)
        return Ticket.objects.create(**data)

    def test_due_at_follows_priority(self):
        for priority, hours in [("high", 4), ("medium", 24), ("low", 72)]:
            with self.subTest(priority=priority):
                ticket = self.make_ticket(priority=priority)
                delta = ticket.due_at - ticket.created_at
                self.assertEqual(delta, timedelta(hours=hours))

    def test_default_priority_gets_due_at(self):
        ticket = self.make_ticket()  # prioridade padrão (média)
        self.assertEqual(ticket.due_at - ticket.created_at, timedelta(hours=24))

    def test_changing_priority_recalculates_due_at(self):
        ticket = self.make_ticket(priority="low")
        self.client.force_login(self.agent)
        self.client.post(
            reverse("tickets:manage", args=[ticket.pk]),
            {"status": "open", "priority": "high"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.due_at - ticket.created_at, timedelta(hours=4))

    def test_is_overdue(self):
        ticket = self.make_ticket()
        Ticket.objects.filter(pk=ticket.pk).update(
            due_at=timezone.now() - timedelta(hours=1)
        )
        ticket.refresh_from_db()
        self.assertTrue(ticket.is_overdue)
        Ticket.objects.filter(pk=ticket.pk).update(status="closed")
        ticket.refresh_from_db()
        self.assertFalse(ticket.is_overdue)

    def test_overdue_filter_and_badge(self):
        late = self.make_ticket(title="Atrasado agora")
        self.make_ticket(title="No prazo")
        Ticket.objects.filter(pk=late.pk).update(
            due_at=timezone.now() - timedelta(hours=1)
        )
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:list") + "?atrasados=1")
        self.assertContains(response, "Atrasado agora")
        self.assertNotContains(response, "No prazo")
        self.assertContains(response, "Atrasado</span>")

    def test_dashboard_access(self):
        url = reverse("tickets:dashboard")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_dashboard_counts(self):
        self.make_ticket(priority="high")
        late = self.make_ticket(title="Atrasado")
        done = self.make_ticket(title="Fechado", status="closed")
        Ticket.objects.filter(pk=late.pk).update(
            due_at=timezone.now() - timedelta(hours=1), assignee=self.agent
        )
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:dashboard"))
        self.assertEqual(response.context["total"], 3)
        self.assertEqual(response.context["open_total"], 2)
        self.assertEqual(response.context["overdue"], 1)
        self.assertEqual(response.context["unassigned"], 1)
        status_rows = dict(response.context["status_rows"])
        self.assertEqual(status_rows["Aberto"], 2)
        self.assertEqual(status_rows["Fechado"], 1)
        agent_rows = dict(response.context["agent_rows"])
        self.assertEqual(agent_rows["carlos"], 1)
        self.assertEqual(agent_rows["Sem responsável"], 1)
        self.assertIsNotNone(done.pk)

    def test_dashboard_link_only_for_agents(self):
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:list"))
        self.assertNotContains(response, reverse("tickets:dashboard"))
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, reverse("tickets:dashboard"))

    def test_history_records_creation_manage_and_assign(self):
        self.client.force_login(self.ana)
        self.client.post(reverse("tickets:create"), {
            "title": "Novo", "category": self.category.pk,
            "priority": "medium", "description": "x",
        })
        ticket = Ticket.objects.get(title="Novo")
        self.assertEqual(ticket.events.first().description, "Chamado aberto")

        self.client.force_login(self.agent)
        self.client.post(reverse("tickets:assign", args=[ticket.pk]))
        self.client.post(
            reverse("tickets:manage", args=[ticket.pk]),
            {"status": "waiting", "priority": "high", "assignee": self.agent.pk},
        )
        texts = [e.description for e in ticket.events.all()]
        self.assertIn("Chamado assumido por carlos", texts)
        self.assertIn("Status alterado de Aberto para Em atendimento", texts)
        self.assertIn(
            "Status alterado de Em atendimento para Aguardando solicitante", texts
        )
        self.assertIn("Prioridade alterado de Média para Alta", texts)

    def test_history_not_logged_when_nothing_changes(self):
        ticket = self.make_ticket()
        self.client.force_login(self.agent)
        self.client.post(
            reverse("tickets:manage", args=[ticket.pk]),
            {"status": "open", "priority": "medium"},
        )
        self.assertEqual(ticket.events.count(), 0)

    def test_history_visible_in_detail(self):
        ticket = self.make_ticket()
        ticket.log(self.agent, "Teste de evento")
        self.client.force_login(self.ana)
        response = self.client.get(reverse("tickets:detail", args=[ticket.pk]))
        self.assertContains(response, "Teste de evento")
