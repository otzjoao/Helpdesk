from django.urls import path

from tickets import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="list"),
    path("novo/", views.TicketCreateView.as_view(), name="create"),
    path("painel/", views.DashboardView.as_view(), name="dashboard"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/comentar/", views.add_comment, name="comment"),
    path("<int:pk>/gerenciar/", views.manage_ticket, name="manage"),
    path("<int:pk>/assumir/", views.assign_to_me, name="assign"),
]
