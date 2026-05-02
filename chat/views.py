from httpx import request
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView, PermissionDenied
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Max, Prefetch
from django.contrib.auth import get_user_model
from .models import CallLog, Conversation, Message,MessageReaction
from .serializers import ContactListInputSerializer, ContactSerializer, ConversationSerializer, MessageSerializer,MessageReactionSerializer,CallLogSerializer
from django.db.models import Q, Prefetch, Max
from django.db.models.functions import Coalesce
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.pagination import PageNumberPagination


User = get_user_model()

class ContactSyncView(GenericAPIView):
    """
    Takes a list of phone numbers and returns registered users matching those numbers.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ContactListInputSerializer 

    def post(self, request, *args, **kwargs):
        # 1. Validate the incoming list of phone numbers
        input_serializer = self.get_serializer(data=request.data)
        
        if input_serializer.is_valid():
            phone_numbers = input_serializer.validated_data['phone_numbers']
            
            # 2. Query the database for users that match the numbers
            matched_users = User.objects.filter(phone_number__in=phone_numbers)
            
            # 3. Serialize the output
            output_serializer = ContactSerializer(matched_users, many=True, context={'request': request})
            
            # 4. Return the custom formatted response
            return Response(
                {
                    "message": "Contacts synced successfully",
                    "data": output_serializer.data
                }, 
                status=status.HTTP_200_OK
            )
            
        # Return 400 Bad Request if the input was invalid
        return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConversationListCreateView(APIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Fetch conversations where the user is either the sender OR receiver,
        # AND they haven't deleted it, AND they haven't archived it.
        conversations = Conversation.objects.prefetch_related(
            Prefetch('messages', queryset=Message.objects.order_by('timestamp'))
        ).annotate(
            latest_time=Coalesce(Max('messages__timestamp'), 'updated_at')
        ).filter(
            (
                Q(sender=user, sender_deleted=False, sender_archived=False)
            ) |
            (
                Q(receiver=user, receiver_deleted=False, receiver_archived=False)
            )
        ).order_by('-latest_time')

        serializer = ConversationSerializer(
            conversations,
            many=True,
            context={'request': request}
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = ConversationSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            conversation = serializer.save(sender=request.user)

            # 2. CRITICAL FIX: You forgot to pass the context when returning the new conversation!
            # Without this, your serializer will crash trying to figure out 'isActive' or 'name'
            response_serializer = ConversationSerializer(
                conversation,
                context={'request': request} 
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ConversationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        user = request.user

        try:
            conversation = Conversation.objects.get(id=pk)
        except Conversation.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        # ✅ check ownership
        if conversation.sender == user:
            conversation.sender_deleted = True
        elif conversation.receiver == user:
            conversation.receiver_deleted = True
        else:
            return Response({"error": "Not allowed"}, status=403)

        conversation.save()

        return Response({"message": "Deleted from your list"})
class ConversationArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        user = request.user

        try:
            conversation = Conversation.objects.get(id=pk)
        except Conversation.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        # Flutter will send {"is_archived": true} or {"is_archived": false}
        # If they don't send it, we default to True
        archive_status = request.data.get('is_archived', True)

        # ✅ Check ownership and update the correct field
        if conversation.sender == user:
            conversation.sender_archived = archive_status
        elif conversation.receiver == user:
            conversation.receiver_archived = archive_status
        else:
            return Response({"error": "Not allowed"}, status=403)

        conversation.save()

        status_text = "archived" if archive_status else "unarchived"
        return Response({
            "message": f"Conversation successfully {status_text}.",
            "is_archived": archive_status
        })
    

class MessageCreateView(APIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = MessageSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            message = serializer.save(sender=request.user)

            return Response(
                MessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConversationMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        user = request.user

        conversation = get_object_or_404(Conversation, id=conversation_id)

        if user != conversation.sender and user != conversation.receiver:
            return Response({"error": "Not allowed"}, status=403)

        messages = conversation.messages.all().order_by('-timestamp')

        paginator = PageNumberPagination()
        paginator.page_size = 20

        page = paginator.paginate_queryset(messages, request)

        serializer = MessageSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)


class MessageUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def patch(self, request, pk):
        message = get_object_or_404(Message, id=pk)

        # ✅ only sender can edit
        if message.sender != request.user:
            return Response({"error": "Not allowed"}, status=403)

        serializer = MessageSerializer(message, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=400)
class MessageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        message = get_object_or_404(Message, id=pk)

        # ✅ only sender can delete
        if message.sender != request.user:
            return Response({"error": "Not allowed"}, status=403)

        message.delete()

        return Response({"message": "Message deleted"})
    
class ToggleReactionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageReactionSerializer

    def post(self, request, message_id):
        message = get_object_or_404(Message, id=message_id)
        user = request.user
        reaction_type = request.data.get('reaction_type')

        if reaction_type not in dict(MessageReaction.MESSAGE_TYPE_CHOICES):
            return Response({"error": "Invalid reaction type"}, status=400)

        # Check if the user has already reacted with the same type
        existing_reaction = MessageReaction.objects.filter(
            message=message,
            user=user,
            reaction_type=reaction_type
        ).first()

        if existing_reaction:
            # If exists, remove the reaction (toggle off)
            existing_reaction.delete()
            return Response({"message": "Reaction removed"})
        else:
            # Otherwise, add the new reaction
            new_reaction = MessageReaction.objects.create(
                message=message,
                user=user,
                reaction_type=reaction_type
            )
            return Response(
                MessageReactionSerializer(new_reaction).data,
                status=status.HTTP_201_CREATED
            )
class ConversationCallView(ListAPIView):
    serializer_class = CallLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        conversation_id = self.kwargs.get("conversation_id")

        return CallLog.objects.filter(
            conversation_id=conversation_id).filter(
                Q(conversation__sender=user) | Q(conversation__receiver=user)).select_related(
                    "caller", "conversation").order_by("-started_at")
    


