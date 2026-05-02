from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q

class Conversation(models.Model):


    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_chat_requests')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_chat_requests')
    
    sender_deleted = models.BooleanField(default=False)   # 👈 new
    receiver_deleted = models.BooleanField(default=False) # 👈 new
    sender_archived = models.BooleanField(default=False)  
    receiver_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A user cannot send multiple requests to the same person
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender} -> {self.receiver}"

    def clean(self):
        # Prevent a user from sending a request to themselves
        if self.sender == self.receiver:
            raise ValidationError("You cannot send a chat request to yourself.")
        if Conversation.objects.filter(
        sender=self.receiver,
        receiver=self.sender).exists():
            raise ValidationError("Conversation already exists between these users.")


class Message(models.Model):

    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('audio_call', 'Audio Call'),
        ('video_call', 'Video Call'),

    ]

    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        related_name='messages'
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_sent'
    )

    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )

    content = models.TextField(blank=True, null=True)  # for text
    file = models.FileField(upload_to='chat/files/', blank=True, null=True)  # for media

    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.message_type} from {self.sender} at {self.timestamp.strftime('%H:%M')}"

class MessageReaction(models.Model):
    REACTION_CHOICES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('haha', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😡'),
    ]

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensures a user can only have one reaction per message
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user} - {self.reaction_type} on Msg {self.message.id}"
    

#group chat models
class Group(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='chat/groups/', blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='groups_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class GroupParticipant(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f"{self.user} in {self.group}"
    

class GroupMessage(models.Model):

    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('audio_call', 'Audio Call'),
        ('video_call', 'Video Call'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_messages_sent'
    )

    message_type = models.CharField(
        max_length=10,
        choices=MESSAGE_TYPE_CHOICES,
        default='text'
    )

    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='chat/group_files/', blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender} in {self.group} at {self.timestamp.strftime('%H:%M')}"
    
class GroupMessageReaction(models.Model):

    REACTION_CHOICES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('haha', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😡'),
    ]

    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user} reacted {self.reaction_type}"

class GroupMessageRead(models.Model):
    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('message', 'user')



import uuid

class CallLog(models.Model):
    """Records every call attempt with outcome and duration."""
 
    CALL_TYPE_CHOICES = [
        ("audio", "Audio"),
        ("video", "Video"),
    ]
 
    STATUS_CHOICES = [
        ("ringing",  "Ringing"),   # initiated, waiting for answer
        ("accepted", "Accepted"),  # callee picked up (connecting WebRTC)
        ("ended",    "Ended"),     # both parties were connected, then ended
        ("rejected", "Rejected"),  # callee declined
        ("missed",   "Missed"),    # callee never answered (timeout)
        ("cancelled","Cancelled"), # caller hung up before callee answered
    ]
 
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation     = models.ForeignKey(
        "Conversation", on_delete=models.CASCADE, related_name="call_logs"
    )
    caller           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_made"
    )
    call_type        = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES, default="audio")
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ringing")
    duration_seconds = models.PositiveIntegerField(default=0)   # filled when call ends
    started_at       = models.DateTimeField(auto_now_add=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    ended_at         = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        db_table = "call_logs"
        ordering = ["-started_at"]
 
    def __str__(self):
        return (
            f"{self.caller} → {self.call_type} call "
            f"[{self.status}] conv={self.conversation_id}"
        )