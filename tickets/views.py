from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView

from tickets.forms import CommentForm, ManageForm, TicketForm
from tickets.models import Ticket
from tickets.permissions import is_agent


def visible_tickets(user):
    """Atendente vê tudo; solicitante vê só os próprios chamados."""
    qs = Ticket.objects.select_related("category", "requester", "assignee")
    return qs if is_agent(user) else qs.filter(requester=user)


class TicketListView(LoginRequiredMixin, ListView):
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 10

    def get_queryset(self):
        qs = visible_tickets(self.request.user)
        status = self.request.GET.get("status")
        if status in Ticket.Status.values:
            qs = qs.filter(status=status)
        if self.request.GET.get("mine") == "1":
            qs = qs.filter(assignee=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Ticket.Status.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["is_agent"] = is_agent(self.request.user)
        return context


class TicketCreateView(LoginRequiredMixin, CreateView):
    form_class = TicketForm
    template_name = "tickets/ticket_form.html"

    def form_valid(self, form):
        form.instance.requester = self.request.user
        response = super().form_valid(form)
        if self.request.user.email:
            send_mail(
                subject=f"[Help Desk] Chamado #{self.object.pk} aberto",
                message=f"Seu chamado '{self.object.title}' foi registrado.",
                from_email=None,
                recipient_list=[self.request.user.email],
            )
        messages.success(self.request, "Chamado aberto com sucesso.")
        return response


class TicketDetailView(LoginRequiredMixin, DetailView):
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        return visible_tickets(self.request.user)  # chamado de outro -> 404

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = is_agent(self.request.user)
        comments = self.object.comments.select_related("author")
        if not agent:
            comments = comments.filter(internal=False)  # nota interna nunca vaza
        context["comments"] = comments
        context["comment_form"] = CommentForm(can_be_internal=agent)
        context["is_agent"] = agent
        if agent:
            context["manage_form"] = ManageForm(instance=self.object)
        return context


@login_required
@require_POST
def add_comment(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = CommentForm(request.POST, can_be_internal=is_agent(request.user))
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()
        ticket.save()  # atualiza updated_at
        notify = (
            not comment.internal
            and ticket.requester.email
            and ticket.requester != request.user
        )
        if notify:
            send_mail(
                subject=f"[Help Desk] Nova resposta no chamado #{ticket.pk}",
                message=comment.body,
                from_email=None,
                recipient_list=[ticket.requester.email],
            )
        messages.success(request, "Comentário adicionado.")
    else:
        messages.error(request, "Escreva uma mensagem antes de enviar.")
    return redirect("tickets:detail", pk=pk)


@login_required
@require_POST
def manage_ticket(request, pk):
    if not is_agent(request.user):
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    form = ManageForm(request.POST, instance=ticket)
    if form.is_valid():
        form.save()
        messages.success(request, "Chamado atualizado.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("tickets:detail", pk=pk)


@login_required
@require_POST
def assign_to_me(request, pk):
    if not is_agent(request.user):
        raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    ticket.assignee = request.user
    if ticket.status == Ticket.Status.OPEN:
        ticket.status = Ticket.Status.IN_PROGRESS
    ticket.save()
    messages.success(request, "Você assumiu este chamado.")
    return redirect("tickets:detail", pk=pk)
