from django.urls import path
from . import views

app_name = 'news'

urlpatterns = [
    path('', views.home, name='home'),
    path('favorites/', views.favorites, name='favorites'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
    path('api/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('api/add-reaction/', views.add_reaction, name='add_reaction'),
    path('api/add-comment/', views.add_comment, name='add_comment'),
    path('api/edit-comment/<int:comment_id>/', views.edit_comment, name='edit_comment'),
    path('api/delete-comment/<int:comment_id>/', views.delete_comment, name='delete_comment'),
]

