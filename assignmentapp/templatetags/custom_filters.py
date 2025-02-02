from django import template

register = template.Library()

@register.filter
def getattr_obj(obj, field_name):
    """Custom filter to get an attribute from a model instance dynamically."""
    return getattr(obj, field_name, None)
@register.filter
def get_meta_fields(model):
    """Returns the fields of a model safely."""
    return model._meta.fields

@register.filter
def getattr_custom(obj, attr_name):
    """Returns the attribute of an object dynamically in templates."""
    return getattr(obj, attr_name, "")

@register.filter(name='getattr')
def getattr_filter(obj, attr):
    """Custom filter to dynamically access an object's attribute."""
    try:
        return getattr(obj, attr, None)  # Returns None if the attribute is not found
    except AttributeError:
        return None