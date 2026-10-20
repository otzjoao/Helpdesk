from django.contrib import admin

from tickets.models import Category, Comment, Ticket


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "priority", "requester", "assignee")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "description", "requester__username")
    inlines = [CommentInline]
