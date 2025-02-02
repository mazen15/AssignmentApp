from celery import shared_task
import csv
from django.db import transaction
from .dynamic_registry import DYNAMIC_MODELS 
from django.apps import apps
from django.db import models, connection, transaction, IntegrityError
import redis
from django.core.mail import send_mail


@shared_task
def process_csv_import(table_name, file_path):
    # r = redis.Redis(host='127.0.0.1', port=6381, db=0)
    # if r.ping():
    #     print("Successfully connected to Redis!")
    # else:
    #     print("Failed to connect to Redis.")
    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return f"Table '{table_name}' not found."

    required_fields = [field.name for field in DynamicModel._meta.fields if not field.null and not field.blank]

    errors = []
    records = []

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Validate required fields
            missing_fields = [field for field in required_fields if not row.get(field)]
            if missing_fields:
                errors.append(f"Missing fields {missing_fields} in row: {row}")
                continue

            # Validate uniqueness (e.g., unique email)
            if "email" in row and DynamicModel.objects.filter(email=row["email"]).exists():
                errors.append(f"Duplicate email: {row['email']} in row: {row}")
                continue

            records.append(DynamicModel(**row))

    # Bulk insert
    if records:
        with transaction.atomic():
            DynamicModel.objects.bulk_create(records, ignore_conflicts=True)
        subject = "Import Completed Successfully"
        message = "Your import has been completed successfully."
        from_email = "mazenbanna15@gmail.com" 
        user_email = "mazenbanna14@gmail.com"  
        html_message = "<strong>Your import is successful!</strong>"

        send_mail(
            subject,
            message,
            from_email,
            [user_email],  # This should be a list of recipient email addresses
            html_message=html_message
        )
    return f"Import completed. {len(records)} records added, {len(errors)} errors."

def get_dynamic_model(table_name):
    """Fetches a dynamic model from cache or Django's registry."""
    table_name = table_name.lower()
    # ✅ First, check the runtime cache
    if table_name in DYNAMIC_MODELS:
        return DYNAMIC_MODELS[table_name]

    # ✅ Then, check Django's model registry
    try:
        return apps.get_model('assignmentapp', table_name)
    except LookupError:
        pass  

    # ✅ Finally, check if the table exists in PostgreSQL
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = %s);", [table_name])
        if cursor.fetchone()[0]:
            print(f"⚠️ Table '{table_name}' exists but model is not registered.")
            return None  # Optionally, reload models from DB
    
    return None
