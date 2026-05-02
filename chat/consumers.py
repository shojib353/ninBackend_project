import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from chat.models import Conversation, Message, MessageReaction

from django.utils import timezone


class StatusConsumer(AsyncWebsocketConsumer):

    
    async def connect(self):
        self.user = self.scope.get("user")

        # ❌ Block unauthenticated users
        if self.user is None or isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4003)
            return

        # ✅ Mark as online immediately
        await self.update_user_status(is_online=True)
        await self.accept()
        print(f"🟢 GLOBALLY ONLINE: {self.user.id}")
        await self.broadcast_status(is_online=True)

    async def disconnect(self, close_code):
        # 🔴 Mark as offline immediately when app is killed/swiped away
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.update_user_status(is_online=False)
            print(f"🔴 GLOBALLY OFFLINE: {self.user.id}")
            await self.broadcast_status(is_online=False)

    # =========================================
    # BROADCAST STATUS TO FRONTEND
    async def broadcast_status(self, is_online):
        """Send a formatted JSON message to the frontend."""
        
        # 1. Create your data dictionary
        data_to_send = {
            "type": "status_update",      # Always include a 'type' so Flutter knows what this is
            "user_id": str(self.user.id),
            "is_online": str(is_online),  # Convert boolean to string for consistency
            "display_text": "Online" if is_online else "Offline"
        }

        # 2. Convert to string and send
        await self.send(text_data=json.dumps(data_to_send))

    # =========================================
    # DATABASE FUNCTIONS
    # =========================================
    @database_sync_to_async
    def update_user_status(self, is_online):
        """Updates the is_online field and last_seen timestamp in the DB."""
        self.user.is_online = is_online
        
        # If they go offline, record exactly when they left
        if not is_online:
            self.user.last_seen = timezone.now()
            self.user.save(update_fields=['is_online', 'last_seen'])
        else:
            self.user.save(update_fields=['is_online'])


import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from .models import Conversation, Message, MessageReaction


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope.get("user")
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Reject unauthenticated users
        if not self.user or isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4003)
            return

        # Check if user is part of this conversation
        if not await self.is_user_in_conversation():
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Optional: Send user online status
        await self.channel_layer.group_send(                        
            self.room_group_name,
            {
                "type": "user_status_event",
                "user_id": str(self.user.id),
                "status": "online"
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Notify others that user went offline
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_status_event",
                "user_id": str(self.user.id),
                "status": "offline"
            }
        )

    # ====================== RECEIVE FROM FLUTTER ======================
    async def send_json(self, content):
        """Helper method to stringify a dictionary and send it as text_data."""
        await self.send(text_data=json.dumps(content))

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
            return

        action = data.get("action")

        if action == "send_message":
            await self.handle_send_message(data)

        elif action == "typing":
            await self.handle_typing(data)

        elif action == "mark_read":
            await self.handle_mark_read(data)

        elif action == "delete_message":
            await self.handle_delete_message(data)

        elif action == "react":
            await self.handle_reaction(data)

        elif action == "ping":
            await self.send_json({"event": "pong"})  # Keep connection alive

    # ====================== MESSAGE HANDLERS ======================

    async def handle_send_message(self, data):
        content = data.get("content")
        message_type = data.get("message_type", "text")
        file_url = data.get("file")

        if not content and message_type == "text":
            await self.send_json({"event": "error", "data": {"message": "Content required"}})
            return

        message_data = await self.save_message(content, message_type, file_url)

        # Broadcast to everyone in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "new_message_event",
                "message": message_data
            }
        )

    async def handle_typing(self, data):
        is_typing = data.get("is_typing", False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_event",
                "user_id": str(self.user.id),
                "is_typing": is_typing
            }
        )

    async def handle_mark_read(self, data):
        message_id = data.get("message_id")
        if message_id:
            await self.mark_message_as_read(message_id)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_read_event",
                    "message_id": message_id,
                    "user_id": str(self.user.id)
                }
            )

    async def handle_delete_message(self, data):
        message_id = data.get("message_id")
        if await self.delete_message(message_id):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_deleted_event",
                    "message_id": message_id
                }
            )

    async def handle_reaction(self, data):
        message_id = data.get("message_id")
        emoji = data.get("emoji")

        reaction_data = await self.add_reaction(message_id, emoji)

        if reaction_data:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "reaction_event",
                    "reaction": reaction_data
                }
            )

    # ====================== SEND EVENTS TO FLUTTER ======================
    async def send_json(self, content):
        """Helper method to stringify a dictionary and send it as text_data."""
        await self.send(text_data=json.dumps(content))


    async def new_message_event(self, event):
        await self.send_json({
            "event": "new_message",
            "data": event["message"]
        })

    async def typing_event(self, event):
        await self.send_json({
            "event": "typing",
            "data": {
                "user_id": event["user_id"],
                "is_typing": event["is_typing"]
            }
        })

    async def message_read_event(self, event):
        await self.send_json({
            "event": "message_read",
            "data": {
                "message_id": event["message_id"],
                "user_id": event["user_id"]
            }
        })

    async def message_deleted_event(self, event):
        await self.send_json({
            "event": "message_deleted",
            "data": {"message_id": event["message_id"]}
        })

    async def reaction_event(self, event):
        await self.send_json({
            "event": "reaction",
            "data": event["reaction"]
        })

    async def user_status_event(self, event):
        print(f"📶 STATUS UPDATE: User {event['user_id']} is now {event['status']}")
        await self.send_json({
            "event": "user_status",
            "data": {
                "user_id": event["user_id"],
                "status": event["status"]
            }
        })

    # ====================== DATABASE OPERATIONS ======================

    @database_sync_to_async
    def is_user_in_conversation(self):
        return Conversation.objects.filter(
            id=self.conversation_id
        ).filter(
            Q(sender=self.user) | Q(receiver=self.user)
        ).exists()

    @database_sync_to_async
    def save_message(self, content, message_type, file_url=None):
        message = Message.objects.create(
            conversation_id=self.conversation_id,
            sender=self.user,
            content=content,
            message_type=message_type,
            file=file_url,
        )

        return {
            "id": str(message.id),
            'conversation_id': str(message.conversation_id),
            "sender": str(message.sender.id),
            "content": message.content,
            "message_type": message.message_type,
            "file": message.file.url if message.file else None,
            "timestamp": message.timestamp.isoformat(),
            "is_read": message.is_read,        
            
        }

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        Message.objects.filter(
            id=message_id,
            conversation_id=self.conversation_id
        ).exclude(sender=self.user).update(is_read=True)

    @database_sync_to_async
    def delete_message(self, message_id):
        try:
            msg = Message.objects.get(id=message_id, conversation_id=self.conversation_id)
            if msg.sender == self.user:
                msg.delete()
                return True
        except Message.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def add_reaction(self, message_id, reaction_type):
        try:
            reaction, _ = MessageReaction.objects.update_or_create(
                message_id=message_id,
                user=self.user,
                defaults={"reaction_type": reaction_type}
            )
            return {
                "message_id": str(message_id),
                "user_id": str(self.user.id),
                "emoji": reaction.reaction_type
            }
        except Exception:
            return None

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.db.models import Q

from .models import Conversation, CallLog

logger = logging.getLogger(__name__)


class CallConsumer(AsyncWebsocketConsumer):
    """
    WebRTC Signaling Server via Django Channels + Redis.

    WebSocket URL:
        ws://yourdomain/ws/call/<conversation_id>/?token=<jwt>

    ┌─────────────────────────────────────────────────────────────┐
    │                    WEBRTC SIGNAL FLOW                       │
    │                                                             │
    │  CALLER                           CALLEE                   │
    │    │                                │                      │
    │    ├── call_initiate ─────────────► │  ◄─ incoming_call    │
    │    │                                │                      │
    │    │  ◄─ call_accepted ─────────────┤ ── call_accept       │
    │    │                                │                      │
    │    ├── offer (SDP) ───────────────► │                      │
    │    │                                │                      │
    │    │  ◄─ answer (SDP) ──────────────┤                      │
    │    │                                │                      │
    │    ├──►  ICE candidates  ◄──────────┤  (both directions)   │
    │    │                                │                      │
    │    │       ══ P2P LIVE ══           │                      │
    │    │                                │                      │
    │    ├── call_end ───────────────────►│  ◄─ call_ended       │
    └─────────────────────────────────────────────────────────────┘
    """

    async def connect(self):
        self.user = self.scope.get("user")
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"call_{self.conversation_id}"
        self._call_log_id = None  # track current call log UUID
        self._call_message_id = None 

        # Reject unauthenticated
        if (
            not self.user
            or isinstance(self.user, AnonymousUser)
            or not self.user.is_authenticated
        ):
            await self.close(code=4003)
            return

        # Reject users not in this conversation
        if not await self.is_user_in_conversation():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(
            "📞 CallConsumer CONNECTED: user=%s conv=%s",
            self.user.id,
            self.conversation_id,
        )

    async def disconnect(self, close_code):
        if not hasattr(self, "room_group_name"):
            return

        # Treat unexpected disconnect as hang-up
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "call_ended_event",
                "ended_by": str(self.user.id),
                "reason": "disconnected",
            },
        )
        await self.update_call_log("ended", 0)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info("📴 CallConsumer DISCONNECTED: user=%s", self.user.id)

    # =========================================================
    # RECEIVE FROM FLUTTER
    # =========================================================

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send({"event": "error", "message": "Invalid JSON"})
            return

        action = data.get("action")
        handlers = {
            "call_initiate": self.handle_call_initiate,
            "call_accept":   self.handle_call_accept,
            "call_reject":   self.handle_call_reject,
            "call_end":      self.handle_call_end,
            "offer":         self.handle_offer,
            "answer":        self.handle_answer,
            "ice_candidate": self.handle_ice_candidate,
            "ping":          self.handle_ping,
        }
        handler = handlers.get(action)
        if handler:
            await handler(data)
        else:
            await self._send({"event": "error", "message": f"Unknown action: {action}"})

    # =========================================================
    # ACTION HANDLERS
    # =========================================================

    async def handle_call_initiate(self, data):
        """
        STEP 1 — Caller starts a call.

        Flutter sends:
          { "action": "call_initiate", "call_type": "audio" | "video" }

        Other party receives:
          {
            "event": "incoming_call",
            "data": {
              "caller_id": "uuid",
              "caller_info": { "name": "...", "avatar": "..." },
              "call_type": "audio" | "video",
              "conversation_id": "7"
            }
          }
        """
        call_type = data.get("call_type", "audio")
        caller_info = await self.get_caller_info()
        self._call_log_id = await self.create_call_log(call_type)
        self._call_message_id = await self.create_call_message(call_type)  

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":            "incoming_call_event",
                "caller_id":       str(self.user.id),
                "caller_info":     caller_info,
                "call_type":       call_type,
                "conversation_id": str(self.conversation_id),
                "call_message_id": str(self._call_message_id),
            },
        )

    async def handle_call_accept(self, data):
        """
        STEP 2 — Callee accepts.

        Flutter sends: { "action": "call_accept" }

        Caller receives:
          { "event": "call_accepted", "data": { "accepted_by": "uuid" } }

        After receiving this, the CALLER must immediately create an SDP offer
        and send: { "action": "offer", "sdp": "..." }
        """
        await self.update_call_log("accepted")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":        "call_accepted_event",
                "accepted_by": str(self.user.id),
            },
        )

    async def handle_call_reject(self, data):
        """
        Callee declines.

        Flutter sends: { "action": "call_reject" }
        Caller receives: { "event": "call_rejected", "data": { "rejected_by": "uuid" } }
        """
        await self.update_call_log("rejected")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":        "call_rejected_event",
                "rejected_by": str(self.user.id),
            },
        )

    async def handle_call_end(self, data):
        """
        Either party hangs up.

        Flutter sends: { "action": "call_end", "duration_seconds": 42 }
        Both parties receive: { "event": "call_ended", "data": { "ended_by": "uuid", "reason": "ended" } }
        """
        duration = data.get("duration_seconds", 0)
        await self.update_call_log("ended", duration)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":     "call_ended_event",
                "ended_by": str(self.user.id),
                "reason":   "ended",
            },
        )

    async def handle_offer(self, data):
        """
        STEP 3 — Caller sends WebRTC SDP offer.

        Flutter sends:
          { "action": "offer", "sdp": "<full SDP string from RTCSessionDescription>" }

        Callee receives:
          { "event": "offer", "data": { "sdp": "...", "from_user": "uuid" } }

        Callee must then call peerConnection.setRemoteDescription(offer),
        create an answer, and send: { "action": "answer", "sdp": "..." }
        """
        sdp = data.get("sdp")
        if not sdp:
            await self._send({"event": "error", "message": "SDP offer required"})
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":      "offer_event",
                "sdp":       sdp,
                "from_user": str(self.user.id),
            },
        )

    async def handle_answer(self, data):
        """
        STEP 4 — Callee sends WebRTC SDP answer.

        Flutter sends:
          { "action": "answer", "sdp": "<full SDP string from RTCSessionDescription>" }

        Caller receives:
          { "event": "answer", "data": { "sdp": "...", "from_user": "uuid" } }

        Caller must then call peerConnection.setRemoteDescription(answer).
        After this, ICE negotiation starts.
        """
        sdp = data.get("sdp")
        if not sdp:
            await self._send({"event": "error", "message": "SDP answer required"})
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":      "answer_event",
                "sdp":       sdp,
                "from_user": str(self.user.id),
            },
        )

    async def handle_ice_candidate(self, data):
        """
        STEP 5 (ongoing) — Both parties exchange ICE candidates.

        Flutter sends:
          {
            "action": "ice_candidate",
            "candidate": {
              "candidate":     "candidate:...",   ← from RTCIceCandidate.candidate
              "sdpMid":        "0",               ← from RTCIceCandidate.sdpMid
              "sdpMLineIndex": 0                  ← from RTCIceCandidate.sdpMLineIndex
            }
          }

        Other party receives:
          { "event": "ice_candidate", "data": { "candidate": {...}, "from_user": "uuid" } }
        """
        candidate = data.get("candidate")
        if not candidate:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type":      "ice_candidate_event",
                "candidate": candidate,
                "from_user": str(self.user.id),
            },
        )

    async def handle_ping(self, data):
        await self._send({"event": "pong"})

    # =========================================================
    # GROUP EVENT HANDLERS  (channel_layer → WebSocket)
    # =========================================================

    async def incoming_call_event(self, event):
        # Only the callee (not the caller) gets this
        if str(self.user.id) != event["caller_id"]:
            await self._send({
                "event": "incoming_call",
                "data": {
                    "caller_id":       event["caller_id"],
                    "caller_info":     event["caller_info"],
                    "call_type":       event["call_type"],
                    "conversation_id": event["conversation_id"],
                },
            })

    async def call_accepted_event(self, event):
        # Only notify the original caller
        if str(self.user.id) != event["accepted_by"]:
            await self._send({
                "event": "call_accepted",
                "data": {"accepted_by": event["accepted_by"]},
            })

    async def call_rejected_event(self, event):
        if str(self.user.id) != event["rejected_by"]:
            await self._send({
                "event": "call_rejected",
                "data": {"rejected_by": event["rejected_by"]},
            })

    async def call_ended_event(self, event):
        # Both parties need to know
        await self._send({
            "event": "call_ended",
            "data": {
                "ended_by": event.get("ended_by", ""),
                "reason":   event.get("reason", "ended"),
            },
        })

    async def offer_event(self, event):
        # Only deliver to the other party, not back to sender
        if str(self.user.id) != event["from_user"]:
            await self._send({
                "event": "offer",
                "data": {
                    "sdp":       event["sdp"],
                    "from_user": event["from_user"],
                },
            })

    async def answer_event(self, event):
        if str(self.user.id) != event["from_user"]:
            await self._send({
                "event": "answer",
                "data": {
                    "sdp":       event["sdp"],
                    "from_user": event["from_user"],
                },
            })

    async def ice_candidate_event(self, event):
        if str(self.user.id) != event["from_user"]:
            await self._send({
                "event": "ice_candidate",
                "data": {
                    "candidate": event["candidate"],
                    "from_user": event["from_user"],
                },
            })

    # =========================================================
    # DATABASE HELPERS
    # =========================================================

    @database_sync_to_async
    def is_user_in_conversation(self):
        return Conversation.objects.filter(
            id=self.conversation_id
        ).filter(
            Q(sender=self.user) | Q(receiver=self.user)
        ).exists()

    @database_sync_to_async
    def get_caller_info(self):
        profile = getattr(self.user, "profile", None)
        return {
            "id":           str(self.user.id),
            "name":         self.user.name or "",
            "display_name": profile.display_name if profile else (self.user.name or ""),
            "avatar":       profile.avatar.url if (profile and profile.avatar) else None,
        }

    @database_sync_to_async
    def create_call_log(self, call_type):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            log = CallLog.objects.create(
                conversation=conversation,
                caller=self.user,
                call_type=call_type,
                status="ringing",
            )
            return log.id
        except Exception as e:
            logger.error("CallLog create error: %s", e)
            return None
    @database_sync_to_async
    def create_call_message(self, call_type):
        """Create a Message record when a call is initiated."""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            call_message_type = "audio_call" if call_type == "audio" else "video_call"

            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                message_type=call_message_type,
                content=f"{call_type.capitalize()} calling...",  # placeholder, updated later
            )
            return message.id
        except Exception as e:
            logger.error("Call message create error: %s", e)
            return None

    # @database_sync_to_async
    # def update_call_log(self, status,):
    #     if not self._call_log_id:
    #         return
    #     try:
    #         CallLog.objects.filter(id=self._call_log_id).update(
    #             status=status,
    #             duration_seconds=duration_seconds,
    #             ended_at=timezone.now() if status in ("ended", "rejected") else None,
    #         )
    #     except Exception as e:
    #         logger.error("CallLog update error: %s", e)
    @database_sync_to_async
    def update_call_log(self, status, duration_seconds=None):
        if not self._call_log_id:
            return

        try:
            log = CallLog.objects.get(id=self._call_log_id)

            log.status = status

            # ✅ When call is accepted → mark connection time
            if status == "accepted":
                log.connected_at = timezone.now()

            # ✅ When call ends → calculate duration from connected_at
            if status in ("ended", "rejected", "missed", "cancelled"):
                log.ended_at = timezone.now()
            

                if log.connected_at:
                    duration = (log.ended_at - log.connected_at).total_seconds()
                    log.duration_seconds = int(duration)
                else:
                    log.duration_seconds = 0  # never connected

            log.save()
                    # ✅ Inline message update — no separate method, no lookup issues
            if self._call_message_id:
                try:
                    message = Message.objects.get(id=self._call_message_id)

                    if status == "ended":
                        if log.duration_seconds:
                            mins, secs = divmod(log.duration_seconds, 60)
                            message.content = (
                                f"Call ended · {mins}m {secs}s" if mins else f"Call ended · {secs}s"
                            )
                        else:
                            message.content = "Call ended"
                    elif status == "missed":
                        message.content = "Missed call"
                    elif status == "rejected":
                        message.content = "Call declined"
                    elif status == "cancelled":
                        message.content = "Call cancelled"
                    else:
                        message.content = f"Call {status}"

                    message.save()

                except Message.DoesNotExist:
                    logger.warning("Call message not found: %s", self._call_message_id)
                except Exception as e:
                    logger.error("Call message update error: %s", e)

        except Exception as e:
            logger.error("CallLog update error: %s", e)
   


 

    # =========================================================
    # UTILITY
    # =========================================================

    async def _send(self, data: dict):
        await self.send(text_data=json.dumps(data))