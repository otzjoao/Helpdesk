# Relatório Técnico — Help Desk em Django

**Disciplina:** Programação Web / Desenvolvimento de Sistemas  
**Projeto:** Help Desk — Sistema de Chamados em Django  
**Integrantes:**Vinicius Durau Ferreira (114.125), Ryan Soler de Lima de Souza (114.038), João Victor dos Santos Ortiz (114.055)  
**Data:** Novembro de 2026

---

## 1. Visão Geral do Projeto

O **Help Desk** é um sistema de gerenciamento de chamados (tickets) desenvolvido em **Django 6.1** com **Python 3.12+**. A aplicação permite que solicitantes abram chamados, atendentes assumam, respondam, mudem status/prioridade/responsável e acompanhem o ciclo de vida até o fechamento.

Funcionalidades principais:
- Autenticação (login/logout) com grupos de permissão
- CRUD de chamados com categorias e prioridades
- Regras de transição de status (máquina de estados)
- SLA (prazo de atendimento) por prioridade com selo "Atrasado"
- Notas internas visíveis apenas para atendentes
- Histórico de eventos (auditoria) por chamado
- Painel do atendente com métricas da fila
- E-mails de notificação (console em desenvolvimento)
- 24 testes automatizados cobrendo regras de negócio

---

## 2. Estrutura do Projeto

```
helpdesk/
│
├── config/                          # Configuração do projeto Django
│   ├── settings.py                  # Settings (apps, DB, auth, email, i18n)
│   ├── urls.py                      # Rotas principais (admin, auth, tickets)
│   ├── asgi.py / wsgi.py            # Entry points ASGI/WSGI
│
├── tickets/                         # App principal
│   ├── models.py                    # Category, Ticket, Comment, TicketEvent
│   ├── permissions.py               # is_agent, AgentRequiredMixin
│   ├── forms.py                     # TicketForm, CommentForm, ManageForm
│   ├── views.py                     # CBVs (ListView, CreateView, DetailView) + FBVs
│   ├── urls.py                      # Rotas do app (namespace 'tickets')
│   ├── admin.py                     # Admin com inlines (Comment, TicketEvent)
│   ├── tests.py                     # 24 testes (TestCase)
│   ├── migrations/                  # 4 migrations (schema + seed + SLA + backfill)
│   ├── templatetags/
│   │   └── ticket_tags.py           # Filtro template: is_agent
│   ├── templates/
│   │   ├── registration/login.html  # Login customizado
│   │   └── tickets/
│   │       ├── base.html            # Layout base (topbar, tema claro/escuro)
│   │       ├── ticket_list.html     # Lista com filtros, chips, paginação
│   │       ├── ticket_form.html     # Formulário de novo chamado
│   │       ├── ticket_detail.html   # Detalhe + conversa + atendimento + histórico
│   │       └── dashboard.html       # Painel do atendente
│   ├── static/tickets/css/
│   │   └── app.css                  # Estilos (CSS Grid/Flex, variáveis CSS, dark mode)
│
├── manage.py                        # CLI do Django
├── requirements.txt                 # Django>=6.1,<6.2
└── README.md                        # Documentação completa
```

---

## 3. Descrição das Principais Partes do Código

### 3.1 Models (`tickets/models.py`)

#### `Category` — Categorias de chamados
```python
class Category(models.Model):
    name = models.CharField("Nome", max_length=60, unique=True)
```
Simples, ordenada por nome, protegida contra exclusão se houver chamados (`PROTECT`).

---

#### `Ticket` — Entidade principal (máquina de estados + SLA)
```python
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

    # Transições válidas (machine de estados)
    TRANSITIONS = {
        "open": {"in_progress", "closed"},
        "in_progress": {"waiting", "resolved", "closed"},
        "waiting": {"in_progress", "closed"},
        "resolved": {"in_progress", "closed"},
        "closed": set(),  # final
    }

    # SLA em horas por prioridade
    SLA_HOURS = {"high": 4, "medium": 24, "low": 72}
    FINAL_STATUSES = ("resolved", "closed")

    title = models.CharField("Título", max_length=120)
    description = models.TextField("Descrição")
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    priority = models.CharField(choices=Priority, default=Priority.MEDIUM)
    status = models.CharField(choices=Status, default=Status.OPEN)
    requester = models.ForeignKey(User, on_delete=PROTECT, related_name="tickets")
    assignee = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL, related_name="assigned_tickets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_at = models.DateTimeField(null=True, blank=True, editable=False)  # SLA
```

**Métodos de negócio:**
```python
def _calc_due_at(self):
    return self.created_at + timedelta(hours=self.SLA_HOURS[str(self.priority)])

def save(self, *args, **kwargs):
    creating = self._state.adding
    if not creating:
        self.due_at = self._calc_due_at()  # recalcula se prioridade mudou
    super().save(*args, **kwargs)
    if creating:
        self.due_at = self._calc_due_at()
        Ticket.objects.filter(pk=self.pk).update(due_at=self.due_at)

@property
def is_overdue(self):
    return (self.due_at and self.status not in self.FINAL_STATUSES 
            and timezone.now() > self.due_at)

def can_change_to(self, new_status):
    return new_status == self.status or new_status in self.TRANSITIONS[self.status]

def log(self, actor, description):
    return TicketEvent.objects.create(ticket=self, actor=actor, description=description)
```

**Conceitos aplicados:**
- **TextChoices** para status/prioridade (type-safe, legível)
- **Máquina de estados** via dicionário `TRANSITIONS`
- **Propriedade computada** `is_overdue` (regra de negócio encapsulada)
- **Recálculo automático de SLA** ao mudar prioridade (no `save`)
- **Auditoria** via método `log()` criando `TicketEvent`

---

#### `Comment` — Comentários (públicos ou internos)
```python
class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=PROTECT)
    body = models.TextField("Mensagem")
    internal = models.BooleanField("Nota interna (só atendentes)", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```
`internal=True` → nota interna, nunca exibida para solicitantes (enforced na view/template).

---

#### `TicketEvent` — Histórico/Auditoria
```python
class TicketEvent(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=CASCADE, related_name="events")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    description = models.CharField("Evento", max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
```
Registra: abertura, assunção, mudanças de status/prioridade/responsável. **Não registra** se nada mudou (`ManageForm.describe_changes()` retorna lista vazia).

---

### 3.2 Permissions (`tickets/permissions.py`)
```python
AGENT_GROUP = "Atendentes"

def is_agent(user):
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name=AGENT_GROUP).exists()

def agents_queryset():
    User = get_user_model()
    return User.objects.filter(
        Q(is_staff=True) | Q(groups__name=AGENT_GROUP), is_active=True
    ).distinct()

class AgentRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_agent(self.request.user)
```
- **RBAC simples**: Atendente = `is_staff` OU grupo "Atendentes"
- `agents_queryset()` usado no `ManageForm` para popular campo `assignee` apenas com atendentes ativos
- `AgentRequiredMixin` protege o painel (`DashboardView`)

---

### 3.3 Forms (`tickets/forms.py`)

#### `TicketForm` — Criação de chamado (solicitante)
```python
class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "category", "priority", "description"]
```
Campos: título, categoria, prioridade, descrição. `requester` definido na view.

---

#### `CommentForm` — Comentários (condicional `internal`)
```python
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body", "internal"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, can_be_internal=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_be_internal:
            del self.fields["internal"]  # solicitante NÃO vê o checkbox
```
**Segurança no formulário**: campo `internal` removido se não for atendente (não apenas escondido no template).

---

#### `ManageForm` — Gestão pelo atendente (status, prioridade, responsável)
```python
class ManageForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["status", "priority", "assignee"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = agents_queryset()

    def clean_status(self):
        new_status = self.cleaned_data["status"]
        if not self.instance.can_change_to(new_status):
            raise forms.ValidationError(
                f"Não é possível ir de '{self.instance.get_status_display()}' "
                f"para '{dict(Ticket.Status.choices)[new_status]}'."
            )
        return new_status

    def describe_changes(self):
        names = {"status": "Status", "priority": "Prioridade", "assignee": "Responsável"}
        labels = {"status": dict(Ticket.Status.choices), "priority": dict(Ticket.Priority.choices)}
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
```
- **Validação de transição** no `clean_status()` usando `Ticket.can_change_to()`
- **Auditoria automática**: `describe_changes()` gera frases para `TicketEvent`
- `assignee` limitado a atendentes ativos

---

### 3.4 Views (`tickets/views.py`)

#### `visible_tickets(user)` — Policy de visibilidade (função utilitária)
```python
def visible_tickets(user):
    qs = Ticket.objects.select_related("category", "requester", "assignee")
    return qs if is_agent(user) else qs.filter(requester=user)
```
Atendente vê **todos**; solicitante vê **apenas seus**. Usado em ListView e DetailView (garante 404 para chamado alheio).

---

#### `TicketListView` — Lista com filtros e paginação
```python
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
        if self.request.GET.get("atrasados") == "1":
            qs = qs.exclude(status__in=Ticket.FINAL_STATUSES).filter(due_at__lt=timezone.now())
        return qs
```
Filtros via query string: `?status=`, `?mine=1`, `?atrasados=1`. Paginação 10 itens.

---

#### `TicketCreateView` — Novo chamado + log + e-mail
```python
class TicketCreateView(LoginRequiredMixin, CreateView):
    form_class = TicketForm
    template_name = "tickets/ticket_form.html"

    def form_valid(self, form):
        form.instance.requester = self.request.user
        response = super().form_valid(form)
        self.object.log(self.request.user, "Chamado aberto")
        if self.request.user.email:
            send_mail(...)
        messages.success(self.request, "Chamado aberto com sucesso.")
        return response
```
Define `requester`, loga abertura, envia e-mail de confirmação.

---

#### `TicketDetailView` — Detalhe + conversa + formulários condicionais
```python
class TicketDetailView(LoginRequiredMixin, DetailView):
    template_name = "tickets/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        return visible_tickets(self.request.user)  # 404 se não tem acesso

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = is_agent(self.request.user)
        comments = self.object.comments.select_related("author")
        if not agent:
            comments = comments.filter(internal=False)  # notas internas nunca vazam
        context["comments"] = comments
        context["events"] = self.object.events.select_related("actor")
        context["comment_form"] = CommentForm(can_be_internal=agent)
        context["is_agent"] = agent
        if agent:
            context["manage_form"] = ManageForm(instance=self.object)
        return context
```
- Filtra comentários internos no **queryset** (não só no template)
- Passa `ManageForm` e `CommentForm` condicionais
- Inclui histórico (`events`)

---

#### `DashboardView` — Painel do atendente (métricas da fila)
```python
class DashboardView(AgentRequiredMixin, TemplateView):
    template_name = "tickets/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        open_qs = Ticket.objects.exclude(status__in=Ticket.FINAL_STATUSES)

        by_status = dict(Ticket.objects.order_by("status").values_list("status").annotate(n=Count("id")))
        by_priority = dict(open_qs.order_by("priority").values_list("priority").annotate(n=Count("id")))
        by_agent = (open_qs.order_by("assignee__username")
                     .values("assignee__username").annotate(n=Count("id")))

        context["total"] = Ticket.objects.count()
        context["open_total"] = open_qs.count()
        context["overdue"] = open_qs.filter(due_at__lt=timezone.now()).count()
        context["unassigned"] = open_qs.filter(assignee__isnull=True).count()
        context["status_rows"] = [(label, by_status.get(value, 0)) for value, label in Ticket.Status.choices]
        context["priority_rows"] = [(label, by_priority.get(value, 0)) for value, label in Ticket.Priority.choices]
        context["agent_rows"] = [(row["assignee__username"] or "Sem responsável", row["n"]) for row in by_agent]
        # max para barras de progresso no template
        for key in ("status", "priority", "agent"):
            counts = [n for _, n in context[f"{key}_rows"]]
            context[f"{key}_max"] = max(counts + [1])
        return context
```
Métricas: total, em andamento, atrasados, sem responsável, distribuição por status/prioridade/responsável. Barras proporcionais no template via `*_max`.

---

#### Function-Based Views (ações POST)

**`add_comment`** — Comentário + e-mail ao solicitante (se não interno)
```python
@login_required @require_POST
def add_comment(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user), pk=pk)
    form = CommentForm(request.POST, can_be_internal=is_agent(request.user))
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()
        ticket.save()  # updated_at
        notify = (not comment.internal and ticket.requester.email and ticket.requester != request.user)
        if notify:
            send_mail(...)
        messages.success(request, "Comentário adicionado.")
    return redirect("tickets:detail", pk=pk)
```

**`manage_ticket`** — Atendente muda status/prioridade/responsável + log
```python
@login_required @require_POST
def manage_ticket(request, pk):
    if not is_agent(request.user): raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    form = ManageForm(request.POST, instance=ticket)
    if form.is_valid():
        changes = form.describe_changes()
        form.save()
        for line in changes:
            ticket.log(request.user, line)
        messages.success(request, "Chamado atualizado.")
    else:
        for errors in form.errors.values():
            for error in errors: messages.error(request, error)
    return redirect("tickets:detail", pk=pk)
```

**`assign_to_me`** — Atendente assume chamado (status → Em atendimento)
```python
@login_required @require_POST
def assign_to_me(request, pk):
    if not is_agent(request.user): raise PermissionDenied
    ticket = get_object_or_404(Ticket, pk=pk)
    if ticket.assignee != request.user:
        ticket.assignee = request.user
        ticket.log(request.user, f"Chamado assumido por {request.user}")
    if ticket.status == Ticket.Status.OPEN:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.log(request.user, "Status alterado de Aberto para Em atendimento")
    ticket.save()
    messages.success(request, "Você assumiu este chamado.")
    return redirect("tickets:detail", pk=pk)
```

---

### 3.5 URLs (`tickets/urls.py` + `config/urls.py`)

**App (`tickets/urls.py`):**
```python
app_name = "tickets"
urlpatterns = [
    path("", TicketListView.as_view(), name="list"),
    path("novo/", TicketCreateView.as_view(), name="create"),
    path("painel/", DashboardView.as_view(), name="dashboard"),
    path("<int:pk>/", TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/comentar/", add_comment, name="comment"),
    path("<int:pk>/gerenciar/", manage_ticket, name="manage"),
    path("<int:pk>/assumir/", assign_to_me, name="assign"),
]
```

**Projeto (`config/urls.py`):**
```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("django.contrib.auth.urls")),  # login, logout, password...
    path("", include("tickets.urls")),  # namespace 'tickets'
]
```

---

### 3.6 Templates (Django Template Language)

#### `base.html` — Layout base (topbar, tema automático, mensagens)
- `meta name="color-scheme" content="light dark"` + CSS variables para dark mode automático
- Topbar com navegação condicional (`{% if user|is_agent %}` via templatetag)
- Avatar com inicial do username
- Logout via **POST** (botão "Sair" no formulário)
- Bloco `messages` para feedback (success/error)

#### `ticket_list.html` — Lista tabular com chips de filtro
- Chips: Todos, status (Aberto, Em atendimento...), Atrasados, Meus (só agente)
- Tabela: #, Título (link), Status (badge), Prioridade (badge), Prazo + selo "Atrasado", Responsável (avatar)
- Paginação com `querystring` preservando filtros

#### `ticket_detail.html` — Layout em duas colunas (main + aside)
- **Main**: Descrição, Conversa (comentários + formulário), tags "nota interna"
- **Aside**: Detalhes (categoria, solicitante, responsável, datas, SLA), Atendimento (botão Assumir + ManageForm), Histórico (timeline ordenada)

#### `dashboard.html` — Cards KPI + tabelas com barras proporcionais
- 4 cards: Total, Em andamento, Atrasados, Sem responsável
- 3 tabelas: Status, Prioridade, Responsável — com barras CSS (`width: calc(100% * count / max)`)

#### `app.css` — CSS moderno sem frameworks
- CSS Variables (`--bg`, `--fg`, `--muted`, `--accent`, `--danger`, `--card`, `--border`)
- `@media (prefers-color-scheme: dark)` para dark mode automático
- Grid/Flexbox, badges, chips, tabelas responsivas, cards, formulários
- Funciona offline (sem CDN)

---

### 3.7 Admin (`tickets/admin.py`)
```python
class CommentInline(admin.TabularInline):
    model = Comment; extra = 0

class EventInline(admin.TabularInline):
    model = TicketEvent; extra = 0; can_delete = False
    readonly_fields = ("actor", "description", "created_at")
    def has_add_permission(self, request, obj=None): return False

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "priority", "due_at", "requester", "assignee")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description", "requester__username")
    readonly_fields = ("due_at",)
    inlines = [CommentInline, EventInline]
```
Comentários e histórico inline no admin. `due_at` readonly (calculado automaticamente).

---

### 3.8 Migrations (Evolução do Schema)

| Migration | Descrição |
|-----------|-----------|
| `0001_initial.py` | Cria `Category`, `Ticket`, `Comment` |
| `0002_seed_data.py` | `RunPython`: cria 5 categorias + grupo "Atendentes" |
| `0003_sla_and_events.py` | Adiciona `Ticket.due_at` + cria modelo `TicketEvent` |
| `0004_fill_due_at.py` | Backfill: calcula `due_at` para chamados existentes |

---

### 3.9 Configuração (`config/settings.py`)
```python
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'tickets',
]

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Campo_Grande'
USE_I18N = True
USE_TZ = True

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'tickets:list'
LOGOUT_REDIRECT_URL = 'login'

# E-mail via console (desenvolvimento)
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'}}
```

---

## 4. Funcionalidades Implementadas

### 4.1 Autenticação e Perfis
| Perfil | Como criar | Permissões |
|--------|------------|------------|
| **Solicitante** | `create_user` comum | Abre chamados, vê apenas os seus, comenta (sem nota interna) |
| **Atendente** | Usuário no grupo `Atendentes` ou `is_staff=True` | Vê todos, assume, gerencia (status/prioridade/responsável), notas internas, painel |
| **Admin** | `createsuperuser` | Tudo + `/admin/` (categorias, usuários) |

---

### 4.2 Ciclo de Vida do Chamado (Máquina de Estados)
```
Aberto → Em atendimento → Aguardando solicitante → Resolvido → Fechado
  ↓           ↓              ↓                      ↓
Fechado ← Fechado ← Fechado ← Fechado ← (Fechado é FINAL)
```
- Validação no `ManageForm.clean_status()` + `Ticket.can_change_to()`
- `Fechado` não permite transição para nenhum outro estado

---

### 4.3 SLA (Service Level Agreement)
| Prioridade | Prazo | Cálculo |
|------------|-------|---------|
| Alta | 4 horas | `created_at + 4h` |
| Média | 24 horas | `created_at + 24h` (padrão) |
| Baixa | 72 horas | `created_at + 72h` |

- Recalculado automaticamente ao mudar prioridade (`Ticket.save()`)
- Propriedade `is_overdue`: `due_at` passou E status não é final
- Filtro `?atrasados=1` + selo "Atrasado" na lista e detalhe

---

### 4.4 Comentários e Notas Internas
- Atendente marca `internal=True` → nota interna
- Solicitante **nunca** vê (filtrado no queryset da DetailView)
- Solicitante **não pode** criar (campo removido do formulário)
- Resposta do atendente (não interna) → e-mail ao solicitante

---

### 4.5 Histórico/Auditoria (`TicketEvent`)
Eventos registrados automaticamente:
1. Criação: "Chamado aberto"
2. Assunção: "Chamado assumido por {user}"
3. Mudança de status: "Status alterado de X para Y"
4. Mudança de prioridade: "Prioridade alterado de X para Y"
5. Mudança de responsável: "Responsável alterado de X para Y"
- **Não registra** se formulário salvo sem alterações (`ManageForm.describe_changes()` vazio)

---

### 4.6 Painel do Atendente (`/painel/`)
- KPIs: Total, Em andamento, Atrasados, Sem responsável
- Distribuição por Status / Prioridade / Responsável
- Barras proporcionais (CSS) usando `*_max` no context
- Acesso restrito: `AgentRequiredMixin` → 403 para solicitante, 302 para anônimo

---

### 4.7 E-mails (Console Backend)
```python
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'}}
```
E-mails aparecem no terminal do `runserver`. Para produção: trocar por SMTP.

---

### 4.8 Testes Automatizados (24 testes — `tickets/tests.py`)
```bash
python manage.py test
# Ran 24 tests ... OK
```
**Cobertura:**
- Acesso: anônimo → login; solicitante vê só seus; atendente vê todos
- Criação: define requester + envia e-mail
- Comentários: interna oculta para solicitante; solicitante não consegue criar interna
- Resposta do atendente → e-mail ao solicitante
- Permissões: solicitante não gerencia (403)
- Assumir: muda para "Em atendimento" + log
- Transições: válidas e inválidas; Fechado é final
- Filtros: status, atrasados
- SLA: due_at por prioridade, padrão, recálculo ao mudar prioridade
- `is_overdue`: verdadeiro se vencido e não final; falso se final
- Painel: acesso (302/403/200), contagens corretas, link visível só para agente
- Histórico: registro na criação, assunção, gestão; nada se sem mudança; visível no detalhe

---

## 5. Conceitos e Padrões Aplicados

| Conceito | Aplicação no Projeto |
|----------|---------------------|
| **MVC/MTV** | Models (`models.py`), Templates (`templates/`), Views (`views.py`) |
| **Class-Based Views** | `ListView`, `CreateView`, `DetailView`, `TemplateView` |
| **Function-Based Views** | Ações POST (`add_comment`, `manage_ticket`, `assign_to_me`) |
| **Mixins** | `LoginRequiredMixin`, `UserPassesTestMixin`, `AgentRequiredMixin` |
| **ORM** | `ForeignKey`, `TextChoices`, `select_related`, `annotate/Count`, `Q` objects |
| **Forms** | `ModelForm`, validação customizada (`clean_status`), campos condicionais |
| **Templates** | Herança (`extends`), blocos, tags (`load static ticket_tags`), filtros (`date`, `timesince`, `slice`) |
| **Templatetags** | `is_agent` filter para lógica no template |
| **Admin** | `TabularInline`, `readonly_fields`, `list_display/filter/search` |
| **Migrations** | Schema + data (`RunPython`), backfill de campo novo |
| **Testes** | `TestCase`, `setUpTestData`, `force_login`, `mail.outbox`, `subTest` |
| **RBAC** | Grupo "Atendentes" + `is_staff` → `is_agent()` |
| **Máquina de Estados** | `TRANSITIONS` dict + validação no form |
| **SLA/Deadline** | Campo `due_at` calculado + property `is_overdue` |
| **Auditoria** | Modelo `TicketEvent` + `log()` + `describe_changes()` |
| **CSS Moderno** | Variáveis CSS, `prefers-color-scheme`, Grid/Flex, sem frameworks |

---

## 6. Como Executar

```bash
# 1. Clonar
git clone https://github.com/otzjoao/helpdesk.git
cd helpdesk

# 2. Ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell

# 3. Dependências
python -m pip install -r requirements.txt  # Django>=6.1,<6.2

# 4. Banco de dados (aplica migrations + seed de categorias/grupo)
python manage.py migrate

# 5. Superusuário (admin)
python manage.py createsuperuser

# 6. Rodar
python manage.py runserver
# Acessar: http://127.0.0.1:8000/
# Admin: http://127.0.0.1:8000/admin/
```

**Testes:**
```bash
python manage.py test  # 24 testes
```

**Vencer prazo de um chamado (para testar "Atrasado"):**
```bash
python manage.py shell -c "
from datetime import timedelta
from django.utils import timezone
from tickets.models import Ticket
Ticket.objects.filter(pk=1).update(due_at=timezone.now() - timedelta(hours=1))
"
```

---

## 7. Conclusão

O projeto demonstra domínio de **Django** aplicado a um sistema real de help desk:

✅ **Autenticação/Autorização** com grupos e mixins  
✅ **Modelagem de domínio** rica (máquina de estados, SLA, auditoria)  
✅ **Views** CBV + FBV com separação de responsabilidades  
✅ **Forms** com validação de regras de negócio (transições, campos condicionais)  
✅ **Templates** responsivos, acessíveis, com dark mode nativo  
✅ **Admin** configurado para gestão completa  
✅ **Testes** abrangentes (24) cobrendo fluxos críticos  
✅ **Migrations** evolutivas com seed de dados e backfill  
✅ **CSS** próprio, moderno, sem dependências externas  

A arquitetura segue as convenções do Django (apps desacoplados, namespace de URLs, `related_name` consistentes) e permite extensões futuras (API REST, anexos, reabertura, deploy) sem refatoração maior.

---

## 8. Anexos — Trechos de Código Relevantes

### 8.1 Diagrama de Entidades (Textual)
```
User (Django auth)
  │
  ├─ 1:N ─► Ticket.requester (Solicitante)
  ├─ 1:N ─► Ticket.assignee (Responsável, nullable)
  ├─ 1:N ─► Comment.author
  └─ 1:N ─► TicketEvent.actor (nullable)

Category 1:N Ticket.category

Ticket 1:N Comment (CASCADE)
Ticket 1:N TicketEvent (CASCADE)
```

### 8.2 Exemplo de Criação de Chamado (POST `/novo/`)
```http
POST /novo/
Content-Type: application/x-www-form-urlencoded

title=Sem+internet&category=3&priority=high&description=Cabo+solto+na+sala+12
```
**Resposta:** `302 Found` → `/1/` (detalhe do chamado criado)  
**E-mail no console:**
```
Content-Type: text/plain; charset="utf-8"
To: ana@x.com
Subject: [Help Desk] Chamado #1 aberto

Seu chamado 'Sem internet' foi registrado.
```

### 8.3 Transição Inválida (Tentativa Aberto → Resolvido)
```python
# ManageForm.clean_status()
ticket.status = "open"
form = ManageForm({"status": "resolved", "priority": "medium"}, instance=ticket)
form.is_valid()  # False
form.errors["status"]  # ["Não é possível ir de 'Aberto' para 'Resolvido'."]
```

### 8.4 SLA Recalculado ao Mudar Prioridade
```python
# Ticket.save() → _calc_due_at()
ticket = Ticket.objects.create(priority="low", ...)  # due_at = created_at + 72h
ticket.priority = "high"
ticket.save()  # due_at recalculado para created_at + 4h
```

### 8.5 Consulta de Chamados Atrasados (ORM)
```python
# TicketListView.get_queryset() para ?atrasados=1
qs = qs.exclude(status__in=Ticket.FINAL_STATUSES).filter(due_at__lt=timezone.now())

# DashboardView - contagem
overdue = open_qs.filter(due_at__lt=timezone.now()).count()
```

### 8.6 Template Tag `is_agent` (templatetags/ticket_tags.py)
```python
@register.filter
def is_agent(user):
    return user.is_authenticated and (user.is_staff or user.groups.filter(name="Atendentes").exists())
```
Uso no template: `{% if user|is_agent %}...{% endif %}`

### 8.7 Exemplo de Histórico (`TicketEvent`)
```
Chamado aberto                                    20/11/2025 10:00 · ana
Chamado assumido por carlos                       20/11/2025 10:05 · carlos
Status alterado de Aberto para Em atendimento     20/11/2025 10:05 · carlos
Prioridade alterado de Média para Alta            20/11/2025 10:10 · carlos
Responsável alterado de ninguém para carlos       20/11/2025 10:10 · carlos
```

---

**Fim do Relatório**  
*Desenvolvido para a disciplina de Programação Web / Desenvolvimento de Sistemas*