from rest_framework import serializers
from .models import Table, Field

class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = ['name', 'field_type', 'is_unique']

class TableSerializer(serializers.ModelSerializer):
    fields = FieldSerializer(many=True, read_only=True)

    class Meta:
        model = Table
        fields = ['name', 'created_at', 'fields']
