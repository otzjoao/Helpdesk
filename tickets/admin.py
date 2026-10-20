from django.contrib import admin

from tickets.models import Category, Comment, Ticket, TicketEvent


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


class EventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "description", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "priority", "due_at", "requester", "assignee")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description", "requester__username")
    readonly_fields = ("due_at",)
    inlines = [CommentInline, EventInline]
