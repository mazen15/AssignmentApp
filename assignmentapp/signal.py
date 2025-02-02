from django.db.models.signals import post_migrate
from django.dispatch import receiver
from apps import load_dynamic_models  # Assume this is the function that loads your dynamic models

# This function will be called when the post_migrate signal is fired
@receiver(post_migrate)
def load_dynamic_models_on_migrate(sender, **kwargs):
    """ ✅ Load dynamic models after migrations have been applied """
    load_dynamic_models()
