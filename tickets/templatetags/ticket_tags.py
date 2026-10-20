from django import template

from tickets.permissions import is_agent

register = template.Library()
register.filter("is_agent", is_agent)
