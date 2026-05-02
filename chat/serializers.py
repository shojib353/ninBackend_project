from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ninUser.models import UserProfile
from .models import CallLog, Conversation, Message, MessageReaction
from django.db.models import Count, Q


User = get_user_model()

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'display_name', 'bio', 'avatar', 'gender',
            'date_of_birth', 'website', 'location',
            'is_private', 'show_last_seen', 'show_read_receipts',
            'allow_calls_from'
        ]

class ContactSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    in_conversation = serializers.SerializerMethodField(read_only=True)
    conversation_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'phone_number', 'name', 'is_verified', 'last_seen', 
                  'profile', 'in_conversation', 'conversation_id']

    def get_in_conversation(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        
        user = request.user
        return Conversation.objects.filter(
            (Q(sender=user) & Q(receiver=obj)) |
            (Q(sender=obj)  & Q(receiver=user))
        ).exists()

    def get_conversation_id(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        
        user = request.user
        conversation = Conversation.objects.filter(
            (Q(sender=user) & Q(receiver=obj)) |
            (Q(sender=obj)  & Q(receiver=user))
        ).first()
        
        return str(conversation.id) if conversation else None


class ContactListInputSerializer(serializers.Serializer):
    phone_numbers = serializers.ListField(
        child=serializers.CharField(max_length=20),
        allow_empty=False,
        help_text="List of phone numbers from the user's contacts"
    )



class ConversationSerializer(serializers.ModelSerializer):
    # Map to your Flutter UI fields
    id = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()
    user_id = serializers.SerializerMethodField()  # Optional: if you want to send the other user's ID
    phone_number = serializers.SerializerMethodField()  # Optional: if you want to send the other user's phone number
    lastMsg = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    avatarUrl = serializers.SerializerMethodField()
    isActive = serializers.SerializerMethodField()
    receiver = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        write_only=True
    )
    is_archived = serializers.SerializerMethodField()

    class Meta:
        model = Conversation  # Ensure you have this imported
        fields = ['id', 'name', 'user_id', 'phone_number', 'lastMsg', 'time','is_archived', 'avatarUrl', 'isActive', 'receiver']
        read_only_fields = ['id', 'name', 'user_id', 'phone_number', 'lastMsg', 'time', 'avatarUrl', 'isActive', 'is_archived']

    def validate(self, attrs):
        request = self.context.get('request')
        sender = request.user
        receiver = attrs.get('receiver')

        # 1. Prevent chatting with yourself
        if sender == receiver:
            raise serializers.ValidationError("You cannot send a chat request to yourself.")

        # 2. Prevent duplicate conversations
        from django.db.models import Q
        conversation_exists = Conversation.objects.filter(
            (Q(sender=sender) & Q(receiver=receiver)) |
            (Q(sender=receiver) & Q(receiver=sender))
        ).exists()

        if conversation_exists:
            raise serializers.ValidationError("A conversation already exists between these users.")

        return attrs

    def _get_other_user(self, obj):
        """Helper method to figure out who the 'other' person is in the chat."""
        request = self.context.get('request')
        if not request or not request.user:
            return None
        
        if obj.sender == request.user:
            return obj.receiver
        return obj.sender
    def get_user_id(self, obj):
        """Fetches the ID of the other user in the conversation."""
        other_user = self._get_other_user(obj)
        return str(other_user.id) if other_user else None

    def get_is_archived(self, obj):
        """Checks if the currently logged-in user has archived this conversation."""
        request = self.context.get('request')
        
        # Safety check to make sure we have the request context
        if not request or not request.user:
            return False

        # If the logged-in user is the sender, check the sender_archived field
        if obj.sender == request.user:
            return obj.sender_archived
            
        # If the logged-in user is the receiver, check the receiver_archived field
        elif obj.receiver == request.user:
            return obj.receiver_archived
            
        return False

    def get_name(self, obj):
        """Fetches the name based on your custom User/UserProfile models."""
        other_user = self._get_other_user(obj)
        if not other_user:
            return "Unknown"
        
        # 1. Try getting the display_name from UserProfile first
        if hasattr(other_user, 'profile') and other_user.profile.display_name:
            return other_user.profile.display_name
        
        # 2. Fallback to the 'name' field on the User model
        if other_user.name:
            return other_user.name
        
        # 3. Last resort fallback to phone number
        return other_user.phone_number
    def get_phone_number(self, obj):
        """Fetches the phone number of the other user in the conversation."""
        other_user = self._get_other_user(obj)
        
        # If the other user exists, return their phone number
        if other_user and other_user.phone_number:
            return other_user.phone_number
            
        # Fallback just in case
        return ""

    def get_lastMsg(self, obj):
        # Fetch the last message using the related_name 'messages'
        last_message = obj.messages.last()
        
        if last_message:
            # Check the message type to return a clean string to Flutter
            if last_message.message_type == 'text':
                return last_message.content or ""
            elif last_message.message_type == 'image':
                return "📷 Image"
            elif last_message.message_type == 'video':
                return "📹 Video"
            elif last_message.message_type == 'audio':
                return "🎵 Audio"
            elif last_message.message_type == 'file':
                return "📄 File"
                
        # Return empty string if there are no messages yet
        return ""

    def get_time(self, obj):
        """Calculates the time difference based on the last message sent."""
        now = timezone.now()
        
        # 1. Fetch the last message
        last_message = obj.messages.last()
        
        # 2. Use the message's timestamp, or fallback to the conversation's updated_at
        if last_message and last_message.timestamp:
            reference_time = last_message.timestamp
        else:
            reference_time = obj.updated_at
            
        # 3. Calculate the difference
        time_difference = now - reference_time
        seconds = time_difference.total_seconds()

        # Just now (less than 60 seconds)
        if seconds < 60:
            return "just now"
        
        # Minutes (less than 60 minutes)
        minutes = int(seconds // 60)
        if minutes < 60:
            return f"{minutes}m"
            
        # Hours (less than 24 hours)
        hours = int(minutes // 60)
        if hours < 24:
            return f"{hours}h"
            
        # Days (less than 7 days)
        days = int(hours // 24)
        if days < 7:
            return f"{days}d"
            
        # Weeks (less than 365 days)
        weeks = int(days // 7)
        if days < 365:
            return f"{weeks}w"
            
        # Years (365+ days)
        years = int(days // 365)
        return f"{years}y"

    def get_avatarUrl(self, obj):
        """Fetches the avatar from your UserProfile model."""
        other_user = self._get_other_user(obj)
        
        if other_user and hasattr(other_user, 'profile') and other_user.profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(other_user.profile.avatar.url)
            return other_user.profile.avatar.url
            
        # Default fallback image matching your Flutter UI
        return "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200"

# 👇 THE ONLY CHANGE NEEDED HERE 👇
    def get_isActive(self, obj):
        """Fetches the real-time online status directly from your new database field."""
        other_user = self._get_other_user(obj)
        if other_user:
            return other_user.is_online
        return False
    



class MessageReactionSerializer(serializers.ModelSerializer):

    class Meta:
        model = MessageReaction
        fields = ['id', 'user', 'message', 'reaction_type', 'timestamp']
        read_only_fields = ['user', 'timestamp']

class MessageSerializer(serializers.ModelSerializer):
    
    
    reactions = MessageReactionSerializer(many=True, read_only=True)
    reaction_counts = serializers.SerializerMethodField()


    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 
            'message_type','content','file', 'is_read', 'timestamp', 'reactions', 'reaction_counts', 
        ]
        read_only_fields = ['id','sender', 'timestamp','content', 'is_read', 'reactions', 'reaction_counts',]
    def get_reaction_counts(self, obj):
        return obj.reactions.count()
    
class CallLogSerializer(serializers.ModelSerializer):
    caller_name = serializers.CharField(source="caller.name", read_only=True)

    class Meta:
        model = CallLog
        fields = [
            "id",
            "conversation",
            "caller",
            "caller_name",
            "call_type",
            "status",
            "duration_seconds",
            "started_at",
            "connected_at",
            "ended_at",
        ]
   
    


# #Group chat serializers
# class GroupParticipantSerializer(serializers.ModelSerializer):
#     user = ContactSerializer(read_only=True)

#     class Meta:
#         model = GroupParticipant
#         fields = ['id', 'user', 'is_admin', 'joined_at']
       


# class GroupSerializer(serializers.ModelSerializer):
#     participants = GroupParticipantSerializer(many=True, read_only=True)
#     class Meta:
#         model = Group
#         fields = ['id', 'name', 'image','participants', 'created_by']
#         read_only_fields = ['id','created_by']


# class GroupMessageSerializer(serializers.ModelSerializer):
#     sender = ContactSerializer(read_only=True)
#     reactions = MessageReactionSerializer(many=True, read_only=True)
#     reaction_counts = serializers.SerializerMethodField()

#     class Meta:
#         model = GroupMessage
#         fields = [
#             'id',
#             'group',
#             'sender',
#             'message_type',
#             'content',
#             'file',
#             'timestamp',
#             'reactions',
#             'reaction_counts',   # ✅ added here
#         ]
#         read_only_fields = ['sender', 'timestamp']

#     def get_reaction_counts(self, obj):
#         counts = {}
#         for reaction in obj.reactions.all():
#             emoji = reaction.emoji
#             counts[emoji] = counts.get(emoji, 0) + 1
#         return counts



