from django.contrib import admin
from .models import CallLog, Conversation, Message, MessageReaction


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'created_at', 'updated_at')
    search_fields = ('sender__phone_number', 'receiver__phone_number')
    list_filter = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    list_select_related = ('sender', 'receiver')  


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender','message_type', 'content','file', 'is_read', 'timestamp')
    search_fields = ('sender__phone_number', 'content')
    list_filter = ('is_read', 'timestamp')
    ordering = ('-timestamp',)
    list_select_related = ('sender', 'conversation') 

    def short_content(self, obj):
        return obj.content[:30]  # limit long text
    short_content.short_description = "Message"


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'user', 'reaction_type', 'timestamp')
    search_fields = ('user__phone_number', 'message__content')
    list_filter = ('reaction_type', 'timestamp')
    ordering = ('-timestamp',)
    list_select_related = ('user', 'message')


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'caller',
        'get_receiver',
        'call_type',
        'status',
        'duration_seconds',
        'started_at',
        'connected_at',
        'ended_at',
    )
    list_filter = ('call_type', 'status', 'started_at')
    search_fields = (
        'caller__phone_number',
        'caller__name',
        'conversation__id',
    )
    readonly_fields = (
        'id',
        'caller',
        'conversation',
        'call_type',
        'status',
        'duration_seconds',
        'started_at',
        'ended_at',
        'connected_at',
    )
    ordering = ('-started_at',)
    date_hierarchy = 'started_at'
 
    # ── Custom columns ────────────────────────────────────────────────────────
 
    @admin.display(description='Receiver')
    def get_receiver(self, obj):
        """Shows the other party in the conversation."""
        conv = obj.conversation
        if conv.sender == obj.caller:
            return conv.receiver
        return conv.sender
 


