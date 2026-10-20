from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

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
