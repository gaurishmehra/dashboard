import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango
import requests
import json
import threading
from datetime import datetime
import warnings
import re
import traceback
import uuid
import os
from pathlib import Path

# ... (ChatMessage, Chat, ChatPersistence classes remain the same as your original) ...
class ChatMessage:
    """Represents a single message with metadata"""
    def __init__(self, role, content, timestamp=None, tool_calls=None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.tool_calls = tool_calls or []  # List of {name, success, details}
    
    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": self.tool_calls
        }
    
    @classmethod
    def from_dict(cls, data):
        msg = cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            tool_calls=data.get("tool_calls", [])
        )
        return msg
    
    def extract_thinking_content(self):
        """Extract thinking content from <think></think> tags, handling nested tags"""
        if not self.content:
            return ""
        
        # Remove all think tags and extract the content between the outermost ones
        content = self.content
        
        # Find the first <think> and last </think>
        first_think = content.find('<think>')
        last_think = content.rfind('</think>')
        
        if first_think != -1 and last_think != -1 and last_think > first_think:
            # Extract content between first <think> and last </think>
            thinking_content = content[first_think + 7:last_think]
            # Remove any nested <think> and </think> tags
            thinking_content = re.sub(r'</?think>', '', thinking_content)
            return thinking_content.strip()
        
        return ""
    
    def extract_main_content(self):
        """Extract main content without any <think></think> tags"""
        if not self.content:
            return ""
        
        content = self.content
        
        # Find the first <think> and last </think>
        first_think = content.find('<think>')
        last_think = content.rfind('</think>')
        
        if first_think != -1 and last_think != -1 and last_think > first_think:
            # Remove everything from first <think> to last </think>
            before_think = content[:first_think]
            after_think = content[last_think + 8:]  # +8 for </think>
            cleaned = (before_think + after_think).strip()
            return cleaned
        
        # If no think tags found, return the whole content
        return content.strip()

class Chat:
    """Represents a single chat session"""
    def __init__(self, chat_id=None, name="New Chat"):
        self.id = chat_id or str(uuid.uuid4())
        self.name = name
        self.messages = []  # List of ChatMessage objects
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
    
    def update_activity(self):
        self.last_activity = datetime.now()
    
    def add_message(self, role, content, tool_calls=None):
        message = ChatMessage(
            role=role, 
            content=content, 
            tool_calls=tool_calls
        )
        self.messages.append(message)
        self.update_activity()
        
        # Auto-name chat based on first user message
        if role == "user" and self.name == "New Chat" and len(self.messages) == 1:
            # Use first 30 characters of first message as name
            clean_content = message.extract_main_content()
            self.name = clean_content[:30] + "..." if len(clean_content) > 30 else clean_content
        
        return message
    
    @property
    def conversation_history(self):
        """Get conversation history in the format expected by the API"""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]
    
    def to_dict(self):
        """Convert chat to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create chat from dictionary (JSON deserialization)"""
        chat = cls(chat_id=data["id"], name=data["name"])
        chat.messages = [ChatMessage.from_dict(msg_data) for msg_data in data.get("messages", [])]
        chat.created_at = datetime.fromisoformat(data["created_at"])
        chat.last_activity = datetime.fromisoformat(data["last_activity"])
        return chat

class ChatPersistence:
    """Handles saving and loading chats to/from filesystem"""
    
    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "mcp_chats"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.cache_dir / "config.json"
    
    def save_chat(self, chat):
        """Save a single chat to disk"""
        try:
            chat_file = self.cache_dir / f"{chat.id}.json"
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save chat {chat.id}: {e}")
            return False
    
    def load_chat(self, chat_id):
        """Load a single chat from disk"""
        try:
            chat_file = self.cache_dir / f"{chat_id}.json"
            if not chat_file.exists():
                return None
            
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return Chat.from_dict(data)
        except Exception as e:
            print(f"[ERROR] Failed to load chat {chat_id}: {e}")
            return None
    
    def load_all_chats(self):
        """Load all chats from disk"""
        chats = {}
        try:
            for chat_file in self.cache_dir.glob("*.json"):
                if chat_file.name == "config.json":
                    continue
                
                chat_id = chat_file.stem
                chat = self.load_chat(chat_id)
                if chat:
                    chats[chat_id] = chat
                else:
                    print(f"[WARNING] Failed to load chat from {chat_file}")
        except Exception as e:
            print(f"[ERROR] Failed to load chats: {e}")
        
        return chats
    
    def delete_chat(self, chat_id):
        """Delete a chat file from disk"""
        try:
            chat_file = self.cache_dir / f"{chat_id}.json"
            if chat_file.exists():
                chat_file.unlink()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete chat {chat_id}: {e}")
            return False
    
    def save_config(self, config):
        """Save configuration (like last opened chat)"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")
            return False
    
    def load_config(self):
        """Load configuration"""
        try:
            if not self.config_file.exists():
                return {}
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")
            return {}
    
    def set_last_opened_chat(self, chat_id):
        """Set the last opened chat ID"""
        config = self.load_config()
        config["last_opened_chat"] = chat_id
        config["last_opened_time"] = datetime.now().isoformat()
        self.save_config(config)
    
    def get_last_opened_chat(self):
        """Get the last opened chat ID"""
        config = self.load_config()
        return config.get("last_opened_chat")

class MCPChatWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.is_active = False
        self.server_url = "http://localhost:8001"
        self.is_streaming = False

        # UI state for streaming
        self.current_assistant_message_box = None
        self.current_message_label = None
        self.current_thinking_expander = None
        self.current_thinking_label = None
        
        # Single buffer for the entire raw response during streaming
        self.current_response_buffer = ""

        # Tool-related state
        self.current_tool_display_widgets = {}
        self.current_tool_calls = []
        
        # Chat management
        self.chats = {}
        self.current_chat_id = None
        self.chat_list_model = Gtk.StringList()
        self.persistence = ChatPersistence()
        
        # UI state
        self.is_renaming = False
        self.rename_entry = None
        
        self.load_chats_from_disk()
        
        if not self.chats:
            self.current_chat_id = self.create_new_chat()
        else:
            last_chat_id = self.persistence.get_last_opened_chat()
            if last_chat_id and last_chat_id in self.chats:
                self.current_chat_id = last_chat_id
            else:
                latest_chat = max(self.chats.values(), key=lambda c: c.last_activity)
                self.current_chat_id = latest_chat.id
        
        self.create_ui()

    # --- START: Parsing logic moved into the widget for live display ---
    def _extract_thinking_content(self, content):
        """Extract thinking content from <think></think> tags for display."""
        if not content:
            return ""
        
        first_think = content.find('<think>')
        last_think = content.rfind('</think>')
        
        if first_think != -1:
            # If we have a closing tag, go up to it. Otherwise, take everything after <think>.
            end_pos = last_think if last_think > first_think else len(content)
            thinking_content = content[first_think + 7:end_pos]
            thinking_content = re.sub(r'</?think>', '', thinking_content)
            return thinking_content.strip()
        
        return ""

    def _extract_main_content(self, content):
        """Extract main content, removing any <think></think> blocks for display."""
        if not content:
            return ""
        
        first_think = content.find('<think>')
        last_think = content.rfind('</think>')
        
        if first_think != -1:
            # If we have a closing tag, remove the whole block.
            if last_think > first_think:
                before_think = content[:first_think]
                after_think = content[last_think + 8:]
                return (before_think + after_think).strip()
            else:
                # If no closing tag yet, just return the content before the opening tag.
                return content[:first_think].strip()
        
        return content.strip()
    # --- END: Parsing logic ---

    def _reset_streaming_state(self):
        """Reset all state variables related to a single streaming response."""
        self.current_assistant_message_box = None
        self.current_message_label = None
        self.current_thinking_expander = None
        self.current_thinking_label = None
        self.current_response_buffer = ""
        self.current_tool_display_widgets = {}
        self.current_tool_calls = []

    def load_chats_from_disk(self):
        """Load all chats from disk"""
        try:
            print("[INFO] Loading chats from disk...")
            self.chats = self.persistence.load_all_chats()
            print(f"[INFO] Loaded {len(self.chats)} chats from disk")
            
            # Validate loaded chats
            valid_chats = {}
            for chat_id, chat in self.chats.items():
                if chat and hasattr(chat, 'id') and hasattr(chat, 'name'):
                    valid_chats[chat_id] = chat
                else:
                    print(f"[WARNING] Invalid chat data for {chat_id}, skipping")
            
            self.chats = valid_chats
            print(f"[INFO] {len(self.chats)} valid chats loaded")
            
        except Exception as e:
            print(f"[ERROR] Failed to load chats from disk: {e}")
            self.chats = {}
    
    def save_chat_to_disk(self, chat_id):
        """Save a specific chat to disk"""
        if chat_id in self.chats:
            success = self.persistence.save_chat(self.chats[chat_id])
            if success:
                print(f"[INFO] Saved chat {chat_id} to disk")
            return success
        else:
            print(f"[WARNING] Attempted to save non-existent chat {chat_id}")
        return False
    
    def save_all_chats_to_disk(self):
        """Save all chats to disk"""
        success_count = 0
        for chat_id, chat in self.chats.items():
            if self.persistence.save_chat(chat):
                success_count += 1
        
        print(f"[INFO] Saved {success_count}/{len(self.chats)} chats to disk")
        return success_count == len(self.chats)
    
    def create_new_chat(self, name="New Chat"):
        """Create a new chat session"""
        chat = Chat(name=name)
        self.chats[chat.id] = chat
        self.save_chat_to_disk(chat.id)
        print(f"[INFO] Created new chat: {chat.id}")
        return chat.id
    
    def get_current_chat(self):
        """Get the currently active chat"""
        if self.current_chat_id and self.current_chat_id in self.chats:
            return self.chats[self.current_chat_id]
        
        # Fallback: if no current chat or invalid, create one
        print(f"[WARNING] No valid current chat (current_id: {self.current_chat_id}), creating new one")
        self.current_chat_id = self.create_new_chat()
        return self.chats[self.current_chat_id]
    
    def switch_to_chat(self, chat_id):
        """Switch to a specific chat"""
        if chat_id in self.chats:
            self.current_chat_id = chat_id
            self.persistence.set_last_opened_chat(chat_id)
            self.refresh_chat_display()
            self.update_chat_list()
            print(f"[INFO] Switched to chat: {self.chats[chat_id].name}")
        else:
            print(f"[ERROR] Attempted to switch to non-existent chat: {chat_id}")
    
    def delete_chat(self, chat_id):
        """Delete a chat session"""
        if chat_id in self.chats and len(self.chats) > 1:
            # Delete from disk first
            self.persistence.delete_chat(chat_id)
            
            # Remove from memory
            del self.chats[chat_id]
            
            # Switch to different chat if this was current
            if self.current_chat_id == chat_id:
                # Switch to most recent chat
                if self.chats:
                    latest_chat = max(self.chats.values(), key=lambda c: c.last_activity)
                    self.current_chat_id = latest_chat.id
                else:
                    # Create new chat if no chats left
                    self.current_chat_id = self.create_new_chat()
                
                self.persistence.set_last_opened_chat(self.current_chat_id)
            
            self.refresh_chat_display()
            self.update_chat_list()
            print(f"[INFO] Deleted chat {chat_id}")
            return True
        return False
    
    def rename_chat(self, chat_id, new_name):
        """Rename a chat session"""
        if chat_id in self.chats:
            old_name = self.chats[chat_id].name
            self.chats[chat_id].name = new_name.strip() or "Unnamed Chat"
            self.chats[chat_id].update_activity()
            self.save_chat_to_disk(chat_id)
            self.update_chat_list()
            print(f"[INFO] Renamed chat from '{old_name}' to '{self.chats[chat_id].name}'")
            return True
        return False
    
    def update_chat_list(self):
        """Update the chat list dropdown"""
        self.chat_list_model.splice(0, self.chat_list_model.get_n_items(), [])
        
        if not self.chats:
            self.chat_list_model.append("No chats available")
            return
        
        # Sort chats by last activity (most recent first)
        sorted_chats = sorted(self.chats.values(), key=lambda c: c.last_activity, reverse=True)
        
        for chat in sorted_chats:
            # Show creation date and message count
            msg_count = len(chat.messages)
            activity_date = chat.last_activity.strftime("%m/%d")
            display_name = f"{chat.name} ({msg_count} msgs, {activity_date})"
            self.chat_list_model.append(display_name)
        
        # Set current selection
        if self.current_chat_id and self.current_chat_id in self.chats:
            current_chat = self.get_current_chat()
            if current_chat:
                sorted_chat_ids = [c.id for c in sorted_chats]
                try:
                    index = sorted_chat_ids.index(self.current_chat_id)
                    self.chat_dropdown.set_selected(index)
                except ValueError:
                    print(f"[WARNING] Current chat {self.current_chat_id} not found in sorted list")
    
    def refresh_chat_display(self):
        """Refresh the chat display with current chat messages"""
        child = self.chat_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.chat_box.remove(child)
            child = next_child
        
        self._reset_streaming_state()
        
        current_chat = self.get_current_chat()
        if current_chat:
            for message in current_chat.messages:
                # Use the permanent display method for loaded messages
                self.add_message_to_display(message)

    def add_message_to_display(self, message):
        """Adds a finalized message to the chat display (for loading from history)."""
        message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                             css_classes=["message-box", f"message-{message.role}"])
        
        # Header (unchanged)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if message.role == "user":
            icon_name, role_text = "avatar-default-symbolic", "You"
            header_box.set_halign(Gtk.Align.END)
        else:
            icon_name, role_text = "computer-symbolic", "Assistant"
            header_box.set_halign(Gtk.Align.START)
        role_icon = Gtk.Image(icon_name=icon_name, pixel_size=16)
        role_label = Gtk.Label(label=role_text, css_classes=["message-role"])
        time_label = Gtk.Label(label=message.timestamp.strftime("%m/%d %H:%M"), css_classes=["time-label"])
        if message.role == "user":
            header_box.append(time_label); header_box.append(role_label); header_box.append(role_icon)
        else:
            header_box.append(role_icon); header_box.append(role_label); header_box.append(time_label)
        message_box.append(header_box)
        
        # Use the message object's own parsing for historical messages
        thinking_content = message.extract_thinking_content()
        if thinking_content:
            expander = Gtk.Expander(label="Thoughts...", expanded=False, css_classes=["thinking-expander"])
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["thinking-content"])
            label = Gtk.Label(label=thinking_content, css_classes=["thinking-text"], wrap=True,
                              wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True, halign=Gtk.Align.START)
            box.append(label)
            expander.set_child(box)
            message_box.append(expander)

        if message.role == "assistant" and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                    css_classes=["tool-usage"], halign=Gtk.Align.START)
                if tool_call.get("success", False):
                    icon, css_class, status = "emblem-ok-symbolic", "tool-success", "Succeeded"
                else:
                    icon, css_class, status = "dialog-error-symbolic", "tool-failure", "Failed"
                tool_box.add_css_class(css_class)
                tool_icon = Gtk.Image(icon_name=icon, pixel_size=14)
                tool_text = Gtk.Label(label=f"Tool: {tool_call['name']} - {status}", css_classes=["tool-label"], halign=Gtk.Align.START)
                tool_box.append(tool_icon)
                tool_box.append(tool_text)
                message_box.append(tool_box)

        main_content = message.extract_main_content()
        if main_content:
            content_label = Gtk.Label(label=main_content, css_classes=["message-content"], wrap=True,
                                    wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True)
            if message.role == "user":
                content_label.set_halign(Gtk.Align.END)
                content_label.set_justify(Gtk.Justification.RIGHT)
            else:
                content_label.set_halign(Gtk.Align.START)
                content_label.set_justify(Gtk.Justification.LEFT)
            message_box.append(content_label)

        self.chat_box.append(message_box)

    def on_send_message(self, widget):
        if self.is_streaming: return
        self.cancel_rename(); self.cancel_delete()
        
        message_text = self.message_entry.get_text().strip()
        if not message_text: return
        
        current_chat = self.get_current_chat()
        if not current_chat:
            self.show_error_message("No active chat session")
            return

        self.message_entry.set_text("")
        
        # Add user message to history and display
        user_message = current_chat.add_message("user", message_text)
        self.add_message_to_display(user_message)
        self.save_chat_to_disk(current_chat.id)
        self.update_chat_list()
        
        self.set_input_enabled(False)
        self._reset_streaming_state()
        threading.Thread(target=self.send_message_streaming, args=(message_text,), daemon=True).start()

    def send_message_streaming(self, message):
        """Sends message and handles the entire streaming response robustly."""
        try:
            current_chat = self.get_current_chat()
            conversation_history = current_chat.conversation_history[:-1] if len(current_chat.messages) > 1 else None
            request_data = {"message": message, "messages": conversation_history, "stream": True}

            GLib.idle_add(self._create_streaming_message_box)

            response = requests.post(f"{self.server_url}/chat", json=request_data, stream=True, timeout=60)
            response.raise_for_status() # Will raise HTTPError for bad responses (4xx or 5xx)

            for line in response.iter_lines():
                if not line: continue
                line_str = line.decode('utf-8')
                if not line_str.startswith('data: '): continue
                
                data_content = line_str[6:]
                if data_content.strip() == '[DONE]': break

                chunk_data = json.loads(data_content)
                chunk_type = chunk_data.get('type', '')
                content = chunk_data.get('content', '')

                if chunk_type in ['thinking', 'content']:
                    cleaned_content = self.clean_content(content)
                    self.current_response_buffer += cleaned_content
                    GLib.idle_add(self._update_streaming_display)
                elif chunk_type == 'tool_call':
                    GLib.idle_add(self.manage_tool_usage_display, chunk_data.get('tool_name', ''), "call")
                elif chunk_type == 'tool_result':
                    GLib.idle_add(self.manage_tool_usage_display, chunk_data.get('tool_name', ''), "result", chunk_data.get('tool_success', False))
                elif chunk_type == 'error':
                    self.show_error_message(f"Stream error: {content}")
                    break

        except requests.exceptions.RequestException as e:
            self.show_error_message(f"Network error: {e}")
        except json.JSONDecodeError as e:
            self.log_error(f"Failed to parse streaming chunk", e)
        except Exception as e:
            self.log_error("Unexpected error in send_message_streaming", e)
            self.show_error_message("An unexpected error occurred.")
        finally:
            GLib.idle_add(self._finalize_stream)

    def _finalize_stream(self):
        """Called after the stream ends, to save the message and re-enable input."""
        current_chat = self.get_current_chat()
        final_content = self.current_response_buffer.strip()

        if final_content or self.current_tool_calls:
            current_chat.add_message(
                "assistant",
                final_content,
                tool_calls=self.current_tool_calls.copy()
            )
            self.save_chat_to_disk(current_chat.id)
            self.update_chat_list()
        
        self.set_input_enabled(True)
        return False # Important for GLib.idle_add

    def _create_streaming_message_box(self):
        """Creates the initial empty message box for the assistant's response."""
        self.current_assistant_message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                                               css_classes=["message-box", "message-assistant"])
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.START)
        header_box.append(Gtk.Image(icon_name="computer-symbolic", pixel_size=16))
        header_box.append(Gtk.Label(label="Assistant", css_classes=["message-role"]))
        header_box.append(Gtk.Label(label=datetime.now().strftime("%m/%d %H:%M"), css_classes=["time-label"]))
        self.current_assistant_message_box.append(header_box)

        # Thinking Expander (initially hidden)
        self.current_thinking_expander = Gtk.Expander(label="Thoughts...", visible=False, css_classes=["thinking-expander"])
        thinking_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["thinking-content"])
        self.current_thinking_label = Gtk.Label(label="", css_classes=["thinking-text"], wrap=True,
                                                 wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True, halign=Gtk.Align.START)
        thinking_box.append(self.current_thinking_label)
        self.current_thinking_expander.set_child(thinking_box)
        self.current_assistant_message_box.append(self.current_thinking_expander)

        # Main content label
        self.current_message_label = Gtk.Label(label="", css_classes=["message-content"], wrap=True,
                                               wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True,
                                               halign=Gtk.Align.START, justify=Gtk.Justification.LEFT)
        self.current_assistant_message_box.append(self.current_message_label)
        
        self.chat_box.append(self.current_assistant_message_box)
        self.scroll_to_bottom()
        return False # for GLib.idle_add

    def _update_streaming_display(self):
        """Parses the full buffer and updates the UI labels accordingly."""
        if not self.current_assistant_message_box:
            return False

        # Parse the entire buffer each time to get the current state
        thinking_part = self._extract_thinking_content(self.current_response_buffer)
        main_part = self._extract_main_content(self.current_response_buffer)

        # Update thinking display
        if thinking_part:
            self.current_thinking_label.set_text(thinking_part)
            if not self.current_thinking_expander.get_visible():
                self.current_thinking_expander.set_visible(True)
        
        # Update main content display
        self.current_message_label.set_text(main_part)

        self.scroll_to_bottom()
        return False # for GLib.idle_add

    def manage_tool_usage_display(self, tool_name, event_type, success=None):
        """Manages the UI for tool calls during streaming."""
        if not self.current_assistant_message_box: return

        if event_type == "call":
            if tool_name in self.current_tool_display_widgets: return
            
            tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                css_classes=["tool-usage", "tool-pending"], halign=Gtk.Align.START)
            tool_icon = Gtk.Image(icon_name="hourglass-symbolic", pixel_size=14)
            tool_text = Gtk.Label(label=f"Calling tool: {tool_name}...", css_classes=["tool-label"], halign=Gtk.Align.START)
            tool_box.append(tool_icon); tool_box.append(tool_text)

            self.current_assistant_message_box.insert_child_after(tool_box, self.current_thinking_expander)

            self.current_tool_display_widgets[tool_name] = {"box": tool_box, "label": tool_text, "icon": tool_icon}
            self.current_tool_calls.append({"name": tool_name, "success": None, "details": {}})
            
        elif event_type == "result":
            if tool_name not in self.current_tool_display_widgets: return
            widgets = self.current_tool_display_widgets[tool_name]
            widgets["box"].remove_css_class("tool-pending")
            
            if success:
                widgets["icon"].set_from_icon_name("emblem-ok-symbolic")
                widgets["box"].add_css_class("tool-success")
                widgets["label"].set_text(f"Tool: {tool_name} - Succeeded")
            else:
                widgets["icon"].set_from_icon_name("dialog-error-symbolic")
                widgets["box"].add_css_class("tool-failure")
                widgets["label"].set_text(f"Tool: {tool_name} - Failed")

            for tool_call in self.current_tool_calls:
                if tool_call["name"] == tool_name:
                    tool_call["success"] = success
                    break
        
        self.scroll_to_bottom()
        return False # for GLib.idle_add

    # --- Other methods (create_ui, scrolling, health checks, etc.) remain largely unchanged ---
    # They are included here for completeness.

    def activate(self):
        if self.is_active: return
        self.is_active = True
        print("MCPChatWidget Activated")
        self.refresh_chat_display()
        self.check_server_health()
    
    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        print("MCPChatWidget Deactivated")
        self.save_all_chats_to_disk()
    
    def create_ui(self):
        # Header with chat management
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                             margin_top=20, margin_bottom=16, margin_start=20, margin_end=20)
        
        # Title and status row
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.title_label = Gtk.Label(label="MCP Chat", halign=Gtk.Align.START, css_classes=["title-large"])
        self.status_label = Gtk.Label(label="Connecting...", halign=Gtk.Align.START, css_classes=["location-label"])
        self.health_label = Gtk.Label(label="Server: Checking...", halign=Gtk.Align.START, css_classes=["dim-label"])
        title_box.append(self.title_label)
        title_box.append(self.status_label)
        title_box.append(self.health_label)
        title_row.append(title_box)
        
        header_box.append(title_row)
        
        # Chat management row
        self.chat_mgmt_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Chat dropdown
        self.chat_dropdown = Gtk.DropDown(model=self.chat_list_model, hexpand=True)
        self.chat_dropdown.connect("notify::selected", self.on_chat_selected)
        self.chat_mgmt_row.append(self.chat_dropdown)
        
        # New chat button
        self.new_chat_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New Chat")
        self.new_chat_btn.add_css_class("circular")
        self.new_chat_btn.connect("clicked", self.on_new_chat)
        self.chat_mgmt_row.append(self.new_chat_btn)
        
        # Rename chat button
        self.rename_chat_btn = Gtk.Button(icon_name="document-edit-symbolic", tooltip_text="Rename Chat")
        self.rename_chat_btn.add_css_class("circular")
        self.rename_chat_btn.connect("clicked", self.on_rename_chat)
        self.chat_mgmt_row.append(self.rename_chat_btn)
        
        # Delete chat button
        self.delete_chat_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Delete Chat")
        self.delete_chat_btn.add_css_class("circular")
        self.delete_chat_btn.add_css_class("destructive-action")
        self.delete_chat_btn.connect("clicked", self.on_delete_chat)
        self.chat_mgmt_row.append(self.delete_chat_btn)
        
        header_box.append(self.chat_mgmt_row)
        
        # Rename entry row (initially hidden)
        self.rename_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.rename_row.set_visible(False)
        
        self.rename_entry = Gtk.Entry(hexpand=True, placeholder_text="Enter new chat name...")
        self.rename_entry.connect("activate", self.on_rename_confirm)
        self.rename_row.append(self.rename_entry)
        
        self.rename_confirm_btn = Gtk.Button(label="✓", tooltip_text="Confirm Rename")
        self.rename_confirm_btn.add_css_class("suggested-action")
        self.rename_confirm_btn.add_css_class("circular")
        self.rename_confirm_btn.connect("clicked", self.on_rename_confirm)
        self.rename_row.append(self.rename_confirm_btn)
        
        self.rename_cancel_btn = Gtk.Button(label="✗", tooltip_text="Cancel Rename")
        self.rename_cancel_btn.add_css_class("circular")
        self.rename_cancel_btn.connect("clicked", self.on_rename_cancel)
        self.rename_row.append(self.rename_cancel_btn)
        
        header_box.append(self.rename_row)
        
        # Delete confirmation row (initially hidden)
        self.delete_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.delete_row.set_visible(False)
        
        self.delete_label = Gtk.Label(label="Delete this chat?", hexpand=True, halign=Gtk.Align.START)
        self.delete_label.add_css_class("warning")
        self.delete_row.append(self.delete_label)
        
        self.delete_confirm_btn = Gtk.Button(label="Delete", tooltip_text="Confirm Delete")
        self.delete_confirm_btn.add_css_class("destructive-action")
        self.delete_confirm_btn.connect("clicked", self.on_delete_confirm)
        self.delete_row.append(self.delete_confirm_btn)
        
        self.delete_cancel_btn = Gtk.Button(label="Cancel", tooltip_text="Cancel Delete")
        self.delete_cancel_btn.connect("clicked", self.on_delete_cancel)
        self.delete_row.append(self.delete_cancel_btn)
        
        header_box.append(self.delete_row)
        
        self.append(header_box)
        
        # Chat area
        self.chat_scrolled = Gtk.ScrolledWindow(vexpand=True, css_classes=["invisible-scroll"])
        self.chat_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                               margin_start=20, margin_end=20, margin_bottom=20)
        
        self.chat_scrolled.set_child(self.chat_box)
        self.append(self.chat_scrolled)
        
        # Input area
        input_frame = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                             margin_start=20, margin_end=20, margin_bottom=20)
        
        self.message_entry = Gtk.Entry(hexpand=True, placeholder_text="Type your message...")
        self.message_entry.connect("activate", self.on_send_message)
        
        self.send_button = Gtk.Button(icon_name="mail-send-symbolic", 
                                     tooltip_text="Send Message",
                                     css_classes=["suggested-action", "circular"])
        self.send_button.connect("clicked", self.on_send_message)
        
        input_frame.append(self.message_entry)
        input_frame.append(self.send_button)
        
        self.append(input_frame)
        
        self.update_chat_list()
    
    def on_chat_selected(self, dropdown, pspec):
        selected = dropdown.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION or not self.chats: return
        sorted_chats = sorted(self.chats.values(), key=lambda c: c.last_activity, reverse=True)
        if selected < len(sorted_chats):
            chat_id = sorted_chats[selected].id
            if chat_id != self.current_chat_id: self.switch_to_chat(chat_id)
    
    def on_new_chat(self, button):
        self.cancel_rename(); self.cancel_delete()
        chat_id = self.create_new_chat()
        self.switch_to_chat(chat_id)
    
    def on_rename_chat(self, button):
        current_chat = self.get_current_chat()
        if not current_chat: return
        self.cancel_delete()
        self.is_renaming = True
        self.rename_entry.set_text(current_chat.name)
        self.rename_row.set_visible(True)
        self.chat_mgmt_row.set_visible(False)
        self.rename_entry.grab_focus()
        self.rename_entry.select_region(0, -1)
    
    def on_rename_confirm(self, widget):
        if not self.is_renaming: return
        current_chat = self.get_current_chat()
        if current_chat:
            new_name = self.rename_entry.get_text().strip()
            if new_name: self.rename_chat(current_chat.id, new_name)
        self.cancel_rename()
    
    def on_rename_cancel(self, button): self.cancel_rename()
    
    def cancel_rename(self):
        self.is_renaming = False
        self.rename_row.set_visible(False)
        self.chat_mgmt_row.set_visible(True)
        self.rename_entry.set_text("")
    
    def on_delete_chat(self, button):
        current_chat = self.get_current_chat()
        if not current_chat or len(self.chats) <= 1: return
        self.cancel_rename()
        self.delete_label.set_text(f"Delete '{current_chat.name}'?")
        self.delete_row.set_visible(True)
        self.chat_mgmt_row.set_visible(False)
    
    def on_delete_confirm(self, button):
        current_chat = self.get_current_chat()
        if current_chat: self.delete_chat(current_chat.id)
        self.cancel_delete()
    
    def on_delete_cancel(self, button): self.cancel_delete()
    
    def cancel_delete(self):
        self.delete_row.set_visible(False)
        self.chat_mgmt_row.set_visible(True)
    
    def log_error(self, error_msg, exception=None):
        print(f"[ERROR] {error_msg}")
        if exception: print(f"[ERROR] Exception details: {traceback.format_exc()}")
    
    def show_error_message(self, message, show_in_chat=True):
        self.log_error(message)
        if show_in_chat:
            GLib.idle_add(lambda: self.show_status_message(f"❌ {message}", is_error=True) or False)
    
    def show_status_message(self, message, is_error=False):
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                               halign=Gtk.Align.CENTER, css_classes=["status-message"])
        icon_name = "dialog-error-symbolic" if is_error else "dialog-information-symbolic"
        status_box.append(Gtk.Image(icon_name=icon_name, pixel_size=16))
        status_box.append(Gtk.Label(label=message, css_classes=["dim-label"]))
        self.chat_box.append(status_box)
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        GLib.timeout_add(50, self._do_scroll)
    
    def _do_scroll(self):
        vadj = self.chat_scrolled.get_vadjustment()
        if vadj: vadj.set_value(vadj.get_upper() - vadj.get_page_size())
        return False

    def check_server_health(self):
        threading.Thread(target=self._check_health_thread, daemon=True).start()

    def _check_health_thread(self):
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "unknown")
                tool_count = data.get("tool_count", 0)
                if status == "healthy":
                    GLib.idle_add(self.update_health, f"Server: Healthy • {tool_count} tools", False)
                else:
                    GLib.idle_add(self.update_health, "Server: Unhealthy", True)
            else:
                GLib.idle_add(self.update_health, "Server: Error", True)
        except requests.exceptions.RequestException:
            GLib.idle_add(self.update_health, "Server: Offline", True)
        except Exception as e:
            self.log_error("Health check failed", e)
            GLib.idle_add(self.update_health, "Server: Unknown Error", True)

    def update_health(self, message, is_error):
        self.health_label.set_text(message)
        self.status_label.set_text("Connected" if not is_error else "Connection Error")
        for label in [self.health_label, self.status_label]:
            if is_error: label.add_css_class("error-label")
            else: label.remove_css_class("error-label")
        return False

    def set_input_enabled(self, enabled):
        self.message_entry.set_sensitive(enabled)
        self.send_button.set_sensitive(enabled)
        self.is_streaming = not enabled

    def clean_content(self, content):
        if not content: return ""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])|\u001b\[[0-9;]*m')
        return ansi_escape.sub('', content)