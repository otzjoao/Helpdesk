from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField("Nome", max_length=60, unique=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        IN_PROGRESS = "in_progress", "Em atendimento"
        WAITING = "waiting", "Aguardando solicitante"
        RESOLVED = "resolved", "Resolvido"
        CLOSED = "closed", "Fechado"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        MEDIUM = "medium", "Média"
        HIGH = "high", "Alta"

    # De qual status pode ir para qual
    TRANSITIONS = {
        "open": {"in_progress", "closed"},
        "in_progress": {"waiting", "resolved", "closed"},
        "waiting": {"in_progress", "closed"},
        "resolved": {"in_progress", "closed"},
        "closed": set(),
    }

    title = models.CharField("Título", max_length=120)
    description = models.TextField("Descrição")
    category = models.ForeignKey(
        Category, verbose_name="Categoria", on_delete=models.PROTECT
    )
    priority = models.CharField(
        "Prioridade", max_length=10, choices=Priority, default=Priority.MEDIUM
    )
    status = models.CharField(
        "Status", max_length=15, choices=Status, default=Status.OPEN
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Solicitante",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Responsável",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Chamado"
        verbose_name_plural = "Chamados"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.title}"

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.pk])

    def can_change_to(self, new_status):
        return new_status == self.status or new_status in self.TRANSITIONS[self.status]


class Comment(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField("Mensagem")
    internal = models.BooleanField("Nota interna (só atendentes)", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comentário"
        verbose_name_plural = "Comentários"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comentário de {self.author} em {self.ticket}"
