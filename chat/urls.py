from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


urlpatterns = [
  
    path('api/contacts/sync/', views.ContactSyncView.as_view(), name='contact-sync'),
    path('conversations/', views.ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('conversations/<int:pk>/', views.ConversationDeleteView.as_view(), name='conversation-delete'),

    #message
    path('messages/', views.MessageCreateView.as_view(), name='send-message'),
    path('conversations/<int:conversation_id>/messages/', views.ConversationMessagesView.as_view(), name='conversation-messages'),
    path('conversations/<int:conversation_id>/calls/',views.ConversationCallView.as_view(),name='conversation-calls'),
    path('conversations/<int:pk>/archive/', views.ConversationArchiveView.as_view(), name='conversation-archive'),
    path('messages/<int:pk>/edit/', views.MessageUpdateView.as_view(), name='edit-message'),
    path('messages/<int:pk>/delete/', views.MessageDeleteView.as_view(), name='delete-message'),
    path('messages/<int:message_id>/reaction/', views.ToggleReactionView.as_view(), name='message-reaction'),
    # path('conversations/<int:conversation_id>/messages/', views.MessageListCreateView.as_view(), name='message-list'),
    # path('conversations/<int:conversation_id>/messages/<int:pk>/', views.MessageDeleteView.as_view(), name='message-delete'),
    # path('messages/<int:message_id>/reaction/', views.ToggleReactionView.as_view(), name='message-reaction'),


# Group Endpoints
    # path('groups/', views.GroupListCreateView.as_view(), name='group-list-create'),

    # # Group Messages Endpoints (GET list, POST create)
    # path('groups/<int:group_id>/messages/', views.GroupMessageListCreateView.as_view(), name='group-messages'),
    # path('groups/<int:pk>/', views.GroupDeleteView.as_view(), name='group-delete'),

    # # Single Message Endpoint (DELETE)
    # path('group-messages/<int:pk>/', views.GroupMessageDeleteView.as_view(), name='group-message-delete'),
    
]