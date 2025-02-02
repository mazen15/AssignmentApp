from django.urls import path
from . import views
from .views import create_table
from .views import delete_table
# from .views import create_table_new
from .views import create_table_test
from .views import edit_table
from .views import delete_table
from .views import delete_dynamic_record
from .views import test_function
from .views import import_csv_view



urlpatterns = [
    #API
    path('api/table/create-table/', create_table, name='create-table'),
    path('api/table/edit-table/', edit_table, name='edit-table'),
    path('api/table/delete-table/', delete_table, name='delete-table'),
    path('table/test/', test_function, name='test'),
    

    #CRUD
    path('dynamic-table/<str:table_name>/delete/<int:record_id>/', delete_dynamic_record, name='dynamic_table_delete'),
    path('dynamic-table/<str:table_name>/edit/<int:record_id>/', views.dynamic_table_edit, name='dynamic_table_edit'),
    path('dynamic-table/<str:table_name>/read/<int:record_id>/', views.dynamic_table_read, name='dynamic_table_read'),
    path('dynamic-table/<str:table_name>/', views.dynamic_table_view, name='dynamic_table_view'),
    path('dynamic-table/<str:table_name>/create/', views.dynamic_table_create, name='dynamic_table_create'),  # New URL for create

    #csv_import
    path('dynamic-table/<str:table_name>/import/', import_csv_view, name='dynamic_table_import'),
]
