from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q

AGENT_GROUP = "Atendentes"


def is_agent(user):
    """Atendente = staff ou membro do grupo 'Atendentes'."""
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
