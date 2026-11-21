from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, english, chinese):
    return chinese if context.get("lang") == "zh" else english


@register.filter
def item(mapping, key):
    return mapping.get(key, "")


@register.filter
def local_stamp(value, precision="minutes"):
    from portal.timezones import format_timestamp
    return format_timestamp(value,seconds=precision=="seconds")
