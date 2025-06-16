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

warnings.filterwarnings("ignore")

class MCPChatWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        
        self.is_active = False
        self.conversation_history = []
        self.server_url = "http://localhost:8001"
        self.current_response = ""
        self.is_streaming = False
        self.current_assistant_message = None
        self.current_message_label = None # Reference to the Gtk.Label holding the assistant's main response
        self.current_thinking_content = ""
        self.current_thinking_expander = None
        self.current_thinking_label = None # Reference to the Gtk.Label inside the thinking expander
        self.current_tool_display_widgets = {} # Stores {tool_name: {"box": Gtk.Box, "label": Gtk.Label, "icon": Gtk.Image}}
        
        self.create_ui()
    
    def activate(self):
        if self.is_active:
            return
        self.is_active = True
        print("MCPChatWidget Activated")
        self.check_server_health()
    
    def deactivate(self):
        if not self.is_active:
            return
        self.is_active = False
        print("MCPChatWidget Deactivated")
    
    def create_ui(self):
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                             margin_top=20, margin_bottom=16, margin_start=20, margin_end=20)
        
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.title_label = Gtk.Label(label="MCP Chat", halign=Gtk.Align.START, css_classes=["title-large"])
        self.status_label = Gtk.Label(label="Connecting...", halign=Gtk.Align.START, css_classes=["location-label"])
        self.health_label = Gtk.Label(label="Server: Checking...", halign=Gtk.Align.START, css_classes=["dim-label"])
        title_box.append(self.title_label)
        title_box.append(self.status_label)
        title_box.append(self.health_label)
        header_box.append(title_box)
        
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
    
    def log_error(self, error_msg, exception=None):
        """Log errors to console and optionally show in UI"""
        print(f"[ERROR] {error_msg}")
        if exception:
            print(f"[ERROR] Exception details: {str(exception)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
    
    def show_error_message(self, message, show_in_chat=True):
        """Show error message in UI"""
        self.log_error(message)
        
        if show_in_chat:
            def show_error():
                self.show_status_message(f"❌ {message}", is_error=True)
                return False
            GLib.idle_add(show_error)
    
    def show_status_message(self, message, is_error=False):
        """Show a status message in the chat area"""
        try:
            status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                halign=Gtk.Align.CENTER, css_classes=["status-message"])
            
            icon_name = "dialog-error-symbolic" if is_error else "dialog-information-symbolic"
            status_icon = Gtk.Image(icon_name=icon_name)
            status_icon.set_pixel_size(16)
            
            status_text = Gtk.Label(label=message, css_classes=["dim-label"])
            
            status_box.append(status_icon)
            status_box.append(status_text)
            
            self.chat_box.append(status_box)
            self.scroll_to_bottom()
        except Exception as e:
            self.log_error(f"Failed to show status message: {message}", e)
    
    def add_message(self, role, content="", is_streaming=False):
        """Add a message to the chat display"""
        try:
            message_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0,
                                 css_classes=["message-box", f"message-{role}"])
            
            # Message header
            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            if role == "user":
                icon_name = "avatar-default-symbolic"
                role_text = "You"
                header_box.set_halign(Gtk.Align.END)
            else:
                icon_name = "computer-symbolic"
                role_text = "Assistant"
                header_box.set_halign(Gtk.Align.START)
            
            role_icon = Gtk.Image(icon_name=icon_name)
            role_icon.set_pixel_size(16)
            role_label = Gtk.Label(label=role_text, css_classes=["message-role"])
            time_label = Gtk.Label(label=datetime.now().strftime("%H:%M"), css_classes=["time-label"])
            
            if role == "user":
                header_box.append(time_label)
                header_box.append(role_label)
                header_box.append(role_icon)
            else:
                header_box.append(role_icon)
                header_box.append(role_label)
                header_box.append(time_label)
            
            message_box.append(header_box)
            
            # For assistant messages, add thinking section first if we have thinking content
            if role == "assistant":
                # Thinking expander (collapsible) - initially hidden
                self.current_thinking_expander = Gtk.Expander(label="Thoughts...")
                self.current_thinking_expander.set_expanded(False)
                self.current_thinking_expander.set_visible(False)
                self.current_thinking_expander.add_css_class("thinking-expander")
                
                self.current_thinking_expander.set_margin_top(0)
                self.current_thinking_expander.set_margin_bottom(0)
                self.current_thinking_expander.set_margin_start(0)
                self.current_thinking_expander.set_margin_end(0)
                
                thinking_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                thinking_box.add_css_class("thinking-content")
                
                thinking_box.set_margin_top(0)
                thinking_box.set_margin_bottom(0)
                thinking_box.set_margin_start(0)
                thinking_box.set_margin_end(0)
                
                self.current_thinking_label = Gtk.Label(label="", css_classes=["thinking-text"])
                self.current_thinking_label.set_wrap(True)
                self.current_thinking_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                self.current_thinking_label.set_selectable(True)
                self.current_thinking_label.set_halign(Gtk.Align.START)
                
                self.current_thinking_label.set_margin_top(0)
                self.current_thinking_label.set_margin_bottom(0)
                self.current_thinking_label.set_margin_start(0)
                self.current_thinking_label.set_margin_end(0)
                
                thinking_box.append(self.current_thinking_label)
                self.current_thinking_expander.set_child(thinking_box)
                message_box.append(self.current_thinking_expander)
            
            # Message content
            content_label = Gtk.Label(label=content, css_classes=["message-content"])
            content_label.set_wrap(True)
            content_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            content_label.set_selectable(True)
            
            content_label.set_margin_top(0)
            content_label.set_margin_bottom(0)
            content_label.set_margin_start(0)
            content_label.set_margin_end(0)
            
            if role == "user":
                content_label.set_halign(Gtk.Align.END)
                content_label.set_justify(Gtk.Justification.RIGHT)
            else:
                content_label.set_halign(Gtk.Align.START)
                content_label.set_justify(Gtk.Justification.LEFT)
            
            message_box.append(content_label)
            
            self.chat_box.append(message_box)
            
            if is_streaming:
                # Store references for streaming updates
                self.current_message_label = content_label
                self.current_assistant_message = message_box
            
            self.scroll_to_bottom()
            return content_label
            
        except Exception as e:
            self.log_error(f"Failed to add message with role '{role}'", e)
            # Fallback: show error in chat
            self.show_error_message("Failed to display message")
            return None
    
    def manage_tool_usage_display(self, tool_name, event_type, success=None):
        """
        Manages the display of tool usage in the chat.
        Args:
            tool_name (str): The name of the tool.
            event_type (str): 'call' when tool is called, 'result' when result is received.
            success (bool, optional): True if tool call was successful, False otherwise. Only relevant for 'result'.
        """
        try:
            if event_type == "call":
                if tool_name in self.current_tool_display_widgets:
                    # Tool call already being displayed, no need to add again
                    return
                
                tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                  css_classes=["tool-usage", "tool-pending"], halign=Gtk.Align.START)
                tool_box.set_margin_top(0)
                tool_box.set_margin_bottom(0)
                tool_box.set_margin_start(0)
                tool_box.set_margin_end(0)
                
                tool_icon = Gtk.Image(icon_name="hourglass-symbolic") 
                tool_icon.set_pixel_size(14)
                
                tool_text = Gtk.Label(label=f"Calling tool: {tool_name}...", css_classes=["tool-label"])
                tool_text.set_halign(Gtk.Align.START)
                
                tool_box.append(tool_icon)
                tool_box.append(tool_text)
                
                # Insert above the main message content, after the thinking expander if present
                if self.current_assistant_message and self.current_message_label:
                    if self.current_thinking_expander and self.current_thinking_expander.get_visible():
                        self.current_assistant_message.insert_child_after(tool_box, self.current_thinking_expander)
                    else:
                        self.current_assistant_message.insert_child_before(tool_box, self.current_message_label)
                else:
                    self.chat_box.append(tool_box)

                self.current_tool_display_widgets[tool_name] = {
                    "box": tool_box,
                    "label": tool_text,
                    "icon": tool_icon
                }
                
            elif event_type == "result":
                if tool_name not in self.current_tool_display_widgets:
                    # This might happen if stream starts mid-way or tool_result comes before tool_call (unlikely)
                    # For robustness, create a new display entry
                    self.log_error(f"Tool result for '{tool_name}' received without prior 'tool_call' entry. Creating new display.")
                    tool_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                                  css_classes=["tool-usage"], halign=Gtk.Align.START)
                    tool_box.set_margin_top(0)
                    tool_box.set_margin_bottom(0)
                    tool_box.set_margin_start(0)
                    tool_box.set_margin_end(0)

                    tool_icon = Gtk.Image()
                    tool_icon.set_pixel_size(14)
                    tool_text = Gtk.Label(css_classes=["tool-label"])
                    tool_text.set_halign(Gtk.Align.START)
                    tool_box.append(tool_icon)
                    tool_box.append(tool_text)
                    
                    if self.current_assistant_message and self.current_message_label:
                        self.current_assistant_message.insert_child_before(tool_box, self.current_message_label)
                    else:
                        self.chat_box.append(tool_box)

                    self.current_tool_display_widgets[tool_name] = {
                        "box": tool_box,
                        "label": tool_text,
                        "icon": tool_icon
                    }
                
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

            self.scroll_to_bottom()
            
        except Exception as e:
            self.log_error(f"Failed to manage tool display for '{tool_name}', event '{event_type}'", e)
    
    def scroll_to_bottom(self):
        """Scroll to the bottom of the chat area"""
        def do_scroll():
            try:
                vadj = self.chat_scrolled.get_vadjustment()
                if vadj:
                    vadj.set_value(vadj.get_upper() - vadj.get_page_size())
            except Exception as e:
                self.log_error("Failed to scroll to bottom", e)
            return False
        
        GLib.timeout_add(50, do_scroll)
    
    def check_server_health(self):
        """Check if the MCP server is running"""
        def check_in_thread():
            try:
                response = requests.get(f"{self.server_url}/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    tool_count = data.get("tool_count", 0)
                    
                    if status == "healthy":
                        GLib.idle_add(self.update_status, f"Connected • {tool_count} tools available", False)
                        GLib.idle_add(self.update_health, f"Server: Healthy • {tool_count} tools", False)
                    else:
                        GLib.idle_add(self.update_status, "Server unhealthy", True)
                        GLib.idle_add(self.update_health, "Server: Unhealthy", True)
                else:
                    error_msg = f"Server returned status {response.status_code}"
                    GLib.idle_add(self.update_status, "Server error", True)
                    GLib.idle_add(self.update_health, "Server: Error", True)
                    self.log_error(error_msg)
                    
            except requests.exceptions.Timeout:
                error_msg = "Server health check timed out"
                GLib.idle_add(self.update_status, "Server timeout", True)
                GLib.idle_add(self.update_health, "Server: Timeout", True)
                self.log_error(error_msg)
                
            except requests.exceptions.ConnectionError:
                error_msg = "Cannot connect to server"
                GLib.idle_add(self.update_status, "Server offline", True)
                GLib.idle_add(self.update_health, "Server: Offline", True)
                self.log_error(error_msg)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Network error during health check: {str(e)}"
                GLib.idle_add(self.update_status, "Network error", True)
                GLib.idle_add(self.update_health, "Server: Network Error", True)
                self.log_error(error_msg, e)
                
            except json.JSONDecodeError as e:
                error_msg = "Invalid response from server"
                GLib.idle_add(self.update_status, "Server error", True)
                GLib.idle_add(self.update_health, "Server: Invalid Response", True)
                self.log_error(error_msg, e)
                
            except Exception as e:
                error_msg = f"Unexpected error during health check: {str(e)}"
                GLib.idle_add(self.update_status, "Unknown error", True)
                GLib.idle_add(self.update_health, "Server: Unknown Error", True)
                self.log_error(error_msg, e)
        
        threading.Thread(target=check_in_thread, daemon=True).start()
    
    def update_health(self, message, is_error):
        """Update the health label"""
        try:
            self.health_label.set_text(message)
            if is_error:
                self.health_label.add_css_class("error-label")
            else:
                self.health_label.remove_css_class("error-label")
        except Exception as e:
            self.log_error(f"Failed to update health label: {message}", e)
    
    def update_status(self, message, is_error):
        """Update the status label"""
        try:
            self.status_label.set_text(message)
            if is_error:
                self.status_label.add_css_class("error-label")
            else:
                self.status_label.remove_css_class("error-label")
        except Exception as e:
            self.log_error(f"Failed to update status label: {message}", e)
    
    def on_send_message(self, widget):
        """Handle sending a message"""
        try:
            if self.is_streaming:
                return
            
            message_text = self.message_entry.get_text().strip()
            if not message_text:
                return
            
            # Clear the entry
            self.message_entry.set_text("")
            
            # Add user message to chat
            if not self.add_message("user", message_text):
                self.show_error_message("Failed to display your message")
                return
            
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": message_text})
            
            # Disable input during processing
            self.set_input_enabled(False)
            
            # Reset streaming state for new message
            self.current_thinking_content = ""
            self.current_tool_display_widgets = {} # Clear tool widgets for new message
            
            # Send message in background thread
            threading.Thread(target=self.send_message_streaming, args=(message_text,), daemon=True).start()
            
        except Exception as e:
            self.log_error("Failed to send message", e)
            self.show_error_message("Failed to send message")
            self.set_input_enabled(True)
    
    def clean_content(self, content):
        """Clean content by removing ANSI codes and think tags"""
        try:
            if not content:
                return ""
            
            # Remove ANSI escape codes
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            cleaned = ansi_escape.sub('', content)
            
            # Remove unicode ANSI codes
            cleaned = re.sub(r'\u001b\[[0-9;]*m', '', cleaned)
            
            # Remove <think> and </think> tags
            cleaned = re.sub(r'<think>', '', cleaned)
            cleaned = re.sub(r'</think>', '', cleaned)
            
            if cleaned.strip():
                return cleaned
            else:
                return ""
                
        except Exception as e:
            self.log_error(f"Failed to clean content: {content[:100]}...", e)
            return content  # Return original if cleaning fails
    
    def update_thinking_content(self, new_content):
        """Update the thinking content in the expander"""
        try:
            if not self.current_thinking_label:
                return
            
            cleaned_content = self.clean_content(new_content)
            if cleaned_content:
                self.current_thinking_content += cleaned_content
                
                def update_label():
                    try:
                        if self.current_thinking_label:
                            self.current_thinking_label.set_text(self.current_thinking_content.strip())
                    except Exception as e:
                        self.log_error("Failed to update thinking label", e)
                    return False
                GLib.idle_add(update_label)
                
                if self.current_thinking_expander and self.current_thinking_content.strip():
                    def show_expander():
                        try:
                            if self.current_thinking_expander:
                                self.current_thinking_expander.set_visible(True)
                        except Exception as e:
                            self.log_error("Failed to show thinking expander", e)
                        return False
                    GLib.idle_add(show_expander)
                    
        except Exception as e:
            self.log_error("Failed to update thinking content", e)
    
    def send_message_streaming(self, message):
        """Send message to server with streaming"""
        try:
            # Prepare request data
            request_data = {
                "message": message,
                "messages": self.conversation_history[:-1] if len(self.conversation_history) > 1 else None,
                "stream": True
            }
            
            # Create assistant message placeholder ONCE
            def create_assistant_message_ui():
                try:
                    self.add_message("assistant", "", is_streaming=True)
                except Exception as e:
                    self.log_error("Failed to create assistant message placeholder", e)
                    self.show_error_message("Failed to create response message")
                return False
            
            GLib.idle_add(create_assistant_message_ui)
            
            # Send streaming request
            try:
                response = requests.post(
                    f"{self.server_url}/chat",
                    json=request_data,
                    stream=True,
                    timeout=60
                )
            except requests.exceptions.Timeout:
                self.show_error_message("Request timed out. Server might be overloaded.")
                return
            except requests.exceptions.ConnectionError:
                self.show_error_message("Cannot connect to server. Check if it's running.")
                return
            except requests.exceptions.RequestException as e:
                self.show_error_message(f"Network error: {str(e)}")
                return
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', f'Server error: {response.status_code}')
                except:
                    error_msg = f"Server error: {response.status_code}"
                self.show_error_message(error_msg)
                return
            
            complete_content = ""
            
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    
                    try:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_content = line[6:]
                            
                            if data_content.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_content)
                                chunk_type = chunk_data.get('type', '')
                                content = chunk_data.get('content', '')
                                
                                if chunk_type == 'thinking':
                                    self.update_thinking_content(content)
                                elif chunk_type == 'content':
                                    cleaned_content = self.clean_content(content)
                                    complete_content += cleaned_content
                                    
                                    def update_content_label():
                                        try:
                                            if self.current_message_label:
                                                # Remove leading whitespace only if it's the beginning of the content
                                                display_content = complete_content.lstrip() if not complete_content.strip() else complete_content
                                                self.current_message_label.set_text(display_content)
                                        except Exception as e:
                                            self.log_error("Failed to update message content", e)
                                        return False
                                    GLib.idle_add(update_content_label)
                                    
                                elif chunk_type == 'tool_call':
                                    tool_name = chunk_data.get('tool_name', '')
                                    if tool_name:
                                        def add_tool_call_display():
                                            self.manage_tool_usage_display(tool_name, "call")
                                            return False
                                        GLib.idle_add(add_tool_call_display)
                                        
                                elif chunk_type == 'tool_result':
                                    tool_name = chunk_data.get('tool_name', '')
                                    tool_success = chunk_data.get('tool_success', False) # Default to False if not present
                                    if tool_name:
                                        def update_tool_result_display():
                                            self.manage_tool_usage_display(tool_name, "result", tool_success)
                                            return False
                                        GLib.idle_add(update_tool_result_display)

                                elif chunk_type == 'complete':
                                    break
                                elif chunk_type == 'error':
                                    error_msg = chunk_data.get('content', 'Unknown streaming error')
                                    self.show_error_message(f"Stream error: {error_msg}")
                                    break
                                    
                            except json.JSONDecodeError as e:
                                self.log_error(f"Failed to parse chunk: {data_content[:100]}...", e)
                                continue
                                
                    except UnicodeDecodeError as e:
                        self.log_error("Failed to decode response line", e)
                        continue
                        
            except Exception as e:
                self.log_error("Error processing response stream", e)
                self.show_error_message("Error processing server response")
                return
            
            # Add to conversation history
            if complete_content.strip():
                self.conversation_history.append({"role": "assistant", "content": complete_content})
            
            # Re-enable input
            GLib.idle_add(lambda: self.set_input_enabled(True) or False)
            
        except Exception as e:
            self.log_error("Unexpected error in send_message_streaming", e)
            self.show_error_message("Unexpected error occurred while sending message")
        finally:
            # Always re-enable input, even if there was an error
            GLib.idle_add(lambda: self.set_input_enabled(True) or False)
    
    def set_input_enabled(self, enabled):
        """Enable or disable input controls"""
        try:
            self.message_entry.set_sensitive(enabled)
            self.send_button.set_sensitive(enabled)
            self.is_streaming = not enabled
        except Exception as e:
            self.log_error(f"Failed to set input enabled state to {enabled}", e)
    
    def handle_response_error(self, error_message):
        """Handle error response (legacy method for backward compatibility)"""
        self.show_error_message(error_message)
        self.set_input_enabled(True)