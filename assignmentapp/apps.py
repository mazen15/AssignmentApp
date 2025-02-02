from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.db import connection
import json
from django.db import models  # Correct import for models, including AutoField
from .dynamic_registry import DYNAMIC_MODELS 

# DYNAMIC_MODELS = {}

def table_exists(table_name):
    """Checks if a table exists in the database."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", 
            [table_name]
        )
        return cursor.fetchone()[0]

class AssignmentappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assignmentapp'

    def ready(self):
        from .dynamic_registry import DYNAMIC_MODELS  # ✅ Import shared storage
        from .models import DynamicTableSchema
        from django.db import models as modelss

        print("🔄 Reloading dynamic models at startup...")

        for schema in DynamicTableSchema.objects.all():
            table_name = schema.table_name.lower()
            if table_name in DYNAMIC_MODELS:
                continue  # Already loaded

            fields = json.loads(schema.fields_json)
            class_name = table_name.capitalize().replace('_', '')

            class Meta:
                app_label = 'assignmentapp'

            attrs = {
                '__module__': 'assignmentapp.models',
                'Meta': Meta,
                'id': modelss.AutoField(primary_key=True),
                'created_at': modelss.DateTimeField(auto_now_add=True),
                'objects': modelss.Manager(),
            }

            for field in fields:
                field_name = field['name']
                field_type = field['field_type']
                if field_type == "text":
                    attrs[field_name] = modelss.CharField(max_length=255)
                elif field_type == "date":
                    attrs[field_name] = modelss.DateField()

            model_class = type(class_name, (modelss.Model,), attrs)

            from . import models
            setattr(models, class_name, model_class)

            DYNAMIC_MODELS[table_name] = model_class
            print(f"✅ Loaded model: {table_name}")

        print("✅ All dynamic models loaded!")


