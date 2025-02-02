from django.db import models
import json
# Create your models here.

class Table(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Field(models.Model):
    table = models.ForeignKey(Table, related_name='fields', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    field_type = models.CharField(max_length=50)
    is_unique = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Test(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DynamicTableSchema(models.Model):
    table_name = models.CharField(max_length=255, unique=True)
    fields_json = models.TextField()  # Store fields as JSON
    created_at = models.DateTimeField(auto_now_add=True)

    def save_fields(self, fields):
        self.fields_json = json.dumps(fields)
        self.save()

    def get_fields(self):
        return json.loads(self.fields_json)