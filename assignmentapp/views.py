from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.db.utils import IntegrityError
from django.apps import apps
from django.http import JsonResponse
from .models import DynamicTableSchema
import json
from django.utils.timezone import now
from .dynamic_registry import DYNAMIC_MODELS 
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db import models, connection, transaction, IntegrityError
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from .tasks import process_csv_import
from .tasks import get_dynamic_model
from django.conf import settings
import logging
from django.core.mail import send_mail




@csrf_exempt
def test_function(request):
    import datetime

    x = datetime.datetime.now()
    DynamicModel = get_dynamic_model("gdrf")
    app_models = apps.get_app_config('assignmentapp').get_models()

    
    if DynamicModel:
        record = DynamicModel.objects.create(name="Test Entry",status="test",created_at=x)  # ✅ Create a record
        records = list(DynamicModel.objects.values())  # ✅ Fetch records

        return JsonResponse({"message": "Record created successfully!", "records": records}, status=201)
    else:
        return JsonResponse({"error": "Model not found!"}, status=400)
 



@api_view(['POST'])
def create_table(request):
    if request.method == 'POST':
        table_name = request.data.get('name').lower()
        fields = request.data.get('fields')

        # Check if table already exists in PostgreSQL
        with connection.cursor() as cursor:
            cursor.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = %s);", [table_name])
            if cursor.fetchone()[0]:  # If table exists
                return JsonResponse({"error": f"Table '{table_name}' already exists."}, status=400)

        # Dynamically create the model class
        class Meta:
            app_label = 'assignmentapp'

        attrs = {
            '__module__': 'assignmentapp.models',
            'Meta': Meta,
            'id': models.AutoField(primary_key=True),
            'created_at': models.DateTimeField(default=now),
            'objects': models.Manager(),
        }

        field_definitions = []
        for field in fields:
            field_name = field.get('name')
            field_type = field.get('field_type')

            if field_type == "text":
                attrs[field_name] = models.CharField(max_length=255)
            elif field_type == "date":
                attrs[field_name] = models.DateField()
            else:
                return JsonResponse({"error": f"Unsupported field type '{field_type}'."}, status=400)

            field_definitions.append({"name": field_name, "field_type": field_type})
        attrs['__module__'] = 'assignmentapp.models'
        # Create and register the dynamic model
        model_class = type(table_name, (models.Model,), attrs)
        # Register in Django's app registry
        apps.all_models['assignmentapp'][table_name] = model_class  # This is the key step to register the model
        
        # Store in runtime cache
        DYNAMIC_MODELS[table_name] = model_class
        # Save the model definition in the database (schema definition)
        DynamicTableSchema.objects.create(table_name=table_name, fields_json=json.dumps(field_definitions))

        # Create the table in the database
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(model_class)

        return JsonResponse({"message": f"Table '{table_name}' created successfully."}, status=201)


@api_view(['POST'])
def edit_table(request):
    
    table_name = request.data.get('name').lower()
    add_fields = request.data.get('add_fields', [])
    remove_fields = request.data.get('remove_fields', [])

    # ✅ Fetch the model dynamically
    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return JsonResponse({"error": f"Table '{table_name}' does not exist."}, status=400)

    # ✅ Modify table schema using schema_editor
    with connection.schema_editor() as schema_editor:
        # ✅ Step 1: Remove Fields
        for field_name in remove_fields:
            if hasattr(DynamicModel, field_name):
                field_obj = DynamicModel._meta.get_field(field_name)
                schema_editor.remove_field(DynamicModel, field_obj)

        # ✅ Step 2: Add Fields
        for field in add_fields:
            field_name = field['name']
            field_type = field['field_type']

            if hasattr(DynamicModel, field_name):
                return JsonResponse({"error": f"Field '{field_name}' already exists."}, status=400)

            if field_type == "text":
                new_field = models.CharField(max_length=255, null=True)
            elif field_type == "date":
                new_field = models.DateField(null=True)
            else:
                return JsonResponse({"error": f"Unsupported field type '{field_type}'."}, status=400)

            new_field.set_attributes_from_name(field_name)
            schema_editor.add_field(DynamicModel, new_field)

    # ✅ Update the schema in the database
    schema_entry = DynamicTableSchema.objects.get(table_name=table_name)
    schema_fields = json.loads(schema_entry.fields_json)

    # ✅ Remove deleted fields from schema
    schema_fields = [f for f in schema_fields if f["name"] not in remove_fields]

    # ✅ Add new fields to schema
    for field in add_fields:
        schema_fields.append({"name": field["name"], "field_type": field["field_type"]})

    schema_entry.fields_json = json.dumps(schema_fields)
    schema_entry.save()

    return JsonResponse({"message": f"Table '{table_name}' updated successfully."}, status=200)

@api_view(['DELETE'])
def delete_table(request):
    
    table_name = request.data.get('name').lower()

    # ✅ Fetch the model dynamically
    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return JsonResponse({"error": f"Table '{table_name}' does not exist."}, status=400)

    # ✅ Drop the table from PostgreSQL
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(DynamicModel)

    # ✅ Remove from Django’s model registry
    try:
        del apps.all_models['assignmentapp'][table_name]
        if table_name in DYNAMIC_MODELS:
            del DYNAMIC_MODELS[table_name]
    except KeyError:
        pass  # Already removed

    # ✅ Delete from `DynamicTableSchema`
    DynamicTableSchema.objects.filter(table_name=table_name).delete()

    return JsonResponse({"message": f"Table '{table_name}' deleted successfully."}, status=200)


from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import DynamicTableSchema


def dynamic_table_view(request, table_name):
    """ View for displaying the table with CRUD operations """
    table_name = table_name.lower()

    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return render(request, 'error.html', {'message': f"Table '{table_name}' not found."})

    # Handling Search functionality
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort_by', 'id') 
    order = request.GET.get('order', 'asc') 

    records = DynamicModel.objects.all()

    # If search query exists, filter by fields dynamically
    if search_query:
    # Create a dynamic Q object to search across all fields
        search_filters = Q()
        for field in DynamicModel._meta.get_fields():
            # Skip the id field and other non-string fields
            if isinstance(field, models.CharField) or isinstance(field, models.TextField):
                search_filters |= Q(**{f"{field.name}__icontains": search_query})

        # Apply the search filter
        records = records.filter(search_filters)

    # Apply Sorting
    if sort_by in [field.name for field in DynamicModel._meta.fields]:  # Ensure sorting only on valid fields
        if order == "desc":
            records = records.order_by(f"-{sort_by}")
        else:
            records = records.order_by(sort_by)

    # Pagination
    paginator = Paginator(records, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get model fields dynamically
    fields = [field.name for field in DynamicModel._meta.fields]

    return render(request, 'dynamic_table.html', {
        'table_name': table_name,
        'records': page_obj,
        'fields': fields,
        'search': search_query,
        'sort_by': sort_by,
        'order': order
    })
def dynamic_table_create(request, table_name):
    """ View to create a new record in a dynamic table """
    table_name = table_name.lower()
    DynamicModel = get_dynamic_model(table_name)

    if not DynamicModel:
        return render(request, 'error.html', {'message': f"Table '{table_name}' not found."})

    if request.method == "POST":
        data = request.POST.dict()
        data.pop('csrfmiddlewaretoken', None)  # Remove CSRF token before inserting data

        try:
            DynamicModel.objects.create(**data)
            return redirect(reverse('dynamic_table_view', kwargs={'table_name': table_name}))  # ✅ Redirect to table list
        except Exception as e:
            return render(request, 'dynamic_table_create.html', {
                'table_name': table_name,
                'fields': [field.name for field in DynamicModel._meta.fields],
                'error': str(e)
            })

    fields = [field.name for field in DynamicModel._meta.fields]
    return render(request, 'dynamic_table_create.html', {
        'table_name': table_name,
        'fields': fields
    })
def dynamic_table_edit(request, table_name, record_id):
    """ View to edit an existing record in the dynamic table """
    table_name = table_name.lower()

    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return render(request, 'error.html', {'message': f"Table '{table_name}' not found."})

    record = DynamicModel.objects.get(id=record_id)

    if request.method == "POST":
        data = request.POST.dict()
        for key, value in data.items():
            setattr(record, key, value)
        record.save()
        return redirect(reverse('dynamic_table_view', kwargs={'table_name': table_name}))

    return render(request, 'dynamic_table_edit.html', {'record': record, 'table_name': table_name})

def dynamic_table_read(request, table_name, record_id):
    """ View to edit an existing record in the dynamic table """
    table_name = table_name.lower()

    DynamicModel = get_dynamic_model(table_name)
    if not DynamicModel:
        return render(request, 'error.html', {'message': f"Table '{table_name}' not found."})

    record = DynamicModel.objects.get(id=record_id)

    return render(request, 'dynamic_table_read.html', {'record': record, 'table_name': table_name})
def delete_dynamic_record(request, table_name, record_id):
    """Delete a specific record from a dynamic table."""
    try:
        DynamicModel = apps.get_model('assignmentapp', table_name)  # Get model
        record = get_object_or_404(DynamicModel, id=record_id)  # Get record
        record.delete()  # Delete record

        return redirect(reverse('dynamic_table_view', kwargs={'table_name': table_name}))
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
        
from django.db import models, connection, transaction, IntegrityError
from django.apps import apps
from rest_framework.response import Response
@api_view(['POST'])
def create_table_test(request):
    if request.method == 'POST':
        table_name = request.data.get('name')
        fields = request.data.get('fields')

        # Ensure the table name is lowercase (Django stores models in lowercase)
        table_name = table_name.lower()

        if table_name in apps.all_models['assignmentapp']:
            return Response({"error": f"Model '{table_name}' already exists."}, status=400)

        class Meta:
            app_label = 'assignmentapp'

        attrs = {
            '__module__': __name__,
            'Meta': Meta,
            '__tablename__': table_name,  # Store table name inside model
            'id': models.AutoField(primary_key=True),  
        }

        field_mapping = {
            "text": lambda f: models.CharField(max_length=255, unique=f.get('is_unique', False)),
            "date": lambda f: models.DateField(),
        }

        for field in fields:
            field_name = field.get('name')
            field_type = field.get('field_type')

            if field_type not in field_mapping:
                return Response({"error": f"Unsupported field type '{field_type}'."}, status=400)

            attrs[field_name] = field_mapping[field_type](field)

        # Dynamically create the model class
        model_class = type(table_name, (models.Model,), attrs)

        try:
            with transaction.atomic():
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(model_class)

            # Register model in Django's ORM
            apps.all_models['assignmentapp'][table_name] = model_class
            setattr(model_class, '_default_manager', models.Manager())  # Add manager

            return Response({"message": f"Table '{table_name}' created successfully."}, status=201)

        except IntegrityError:
            return Response({"error": "Table with this name already exists."}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=500)




def import_csv_view(request, table_name):
    import redis

    r = redis.Redis(host='127.0.0.1', port=6381, db=0)
    print(r.ping()) 
    if request.method == "POST" and request.FILES.get("csv_file"):
        csv_file = request.FILES["csv_file"]
        if not csv_file.name.endswith(".csv"):
            return render(request, "import_csv.html", {"error": "Only CSV files are allowed."})

        fs = FileSystemStorage()
        file_path = fs.save(csv_file.name, csv_file)
        print(file_path)
        process_csv_import(table_name, file_path)
        # process_csv_import.delay(table_name, file_path)
        
        return render(request, "import_csv.html", {"message": "Import started. Check logs for status."})

    return render(request, "import_csv.html", {"table_name": table_name})

def send_success_email(user_email):
    subject = "Data Import Completed Successfully"
    message = "Your data import has been successfully completed."
    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(subject, message, from_email, [user_email])
    except Exception as e:
        print('error Sending Email')
