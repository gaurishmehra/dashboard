import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, GdkPixbuf, Gio, Gdk
import json
import os
from datetime import datetime, timedelta
import warnings
import subprocess

# Suppress deprecation warnings
warnings.filterwarnings("ignore", ".*set_from_pixbuf.*", DeprecationWarning)

class NotificationRow(Gtk.ListBoxRow):
    def __init__(self, notification):
        super().__init__()
        self.notification = notification
        self.expanded = False
        
        self.set_activatable(True)
        self.add_css_class("notification-row")
        
        self.create_ui()
    
    def create_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_top(12)
        header_box.set_margin_bottom(12)
        header_box.set_margin_start(16)
        header_box.set_margin_end(16)
        
        # --- CHANGE 1: Use Adw.Avatar instead of Gtk.Image ---
        # It's circular by default and handles images, icons, and text fallbacks.
        self.avatar = Adw.Avatar(size=48)
        self.avatar.set_halign(Gtk.Align.CENTER)
        self.avatar.set_valign(Gtk.Align.CENTER)
        
        self.load_icon()
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.set_hexpand(True)
        content_box.set_valign(Gtk.Align.CENTER)
        
        header_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        app_name_label = Gtk.Label(label=self.notification.get('app_name', 'Unknown'))
        app_name_label.set_halign(Gtk.Align.START)
        app_name_label.add_css_class("app-name")
        
        time_str = self.format_timestamp()
        time_label = Gtk.Label(label=time_str)
        time_label.set_halign(Gtk.Align.END)
        time_label.add_css_class("time-label")
        
        header_info.append(app_name_label)
        header_info.append(time_label)
        
        summary_label = Gtk.Label(label=self.notification.get('summary', 'No title'))
        summary_label.set_halign(Gtk.Align.START)
        summary_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_label.set_max_width_chars(45)
        summary_label.add_css_class("summary-label")
        
        content_box.append(header_info)
        content_box.append(summary_label)
        
        self.expand_icon = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        self.expand_icon.add_css_class("expand-icon")
        self.expand_icon.set_size_request(16, 16)
        self.expand_icon.set_valign(Gtk.Align.CENTER)
        
        header_box.append(self.avatar) # Add the avatar here
        header_box.append(content_box)
        header_box.append(self.expand_icon)
        
        main_box.append(header_box)
        
        # ... (rest of the create_ui method is unchanged)
        body_text = self.notification.get('body', '')
        if body_text:
            self.body_revealer = Gtk.Revealer()
            self.body_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            self.body_revealer.set_transition_duration(200)
            self.body_revealer.set_reveal_child(False)
            
            body_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            body_container.set_margin_start(76)
            body_container.set_margin_end(16)
            body_container.set_margin_bottom(16)
            
            estimated_lines = len(body_text) / 60
            
            if estimated_lines > 5:
                scrolled_body = Gtk.ScrolledWindow()
                scrolled_body.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scrolled_body.set_max_content_height(120)
                scrolled_body.set_min_content_height(80)
                scrolled_body.add_css_class("notification-body-scroll")
                
                body_label = Gtk.Label(label=body_text)
                body_label.set_halign(Gtk.Align.START)
                body_label.set_wrap(True)
                body_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                body_label.set_max_width_chars(55)
                body_label.add_css_class("body-label")
                body_label.set_margin_top(8)
                body_label.set_margin_bottom(8)
                body_label.set_margin_start(8)
                body_label.set_margin_end(8)
                
                scrolled_body.set_child(body_label)
                body_container.append(scrolled_body)
            else:
                body_label = Gtk.Label(label=body_text)
                body_label.set_halign(Gtk.Align.START)
                body_label.set_wrap(True)
                body_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                body_label.set_max_width_chars(55)
                body_label.add_css_class("body-label")
                body_container.append(body_label)
            
            self.body_revealer.set_child(body_container)
            main_box.append(self.body_revealer)
        else:
            self.body_revealer = None
        
        self.set_child(main_box)
    
    def load_icon(self):
        """Load icon into the Adw.Avatar widget."""
        try:
            icon_path = self.notification.get('icon', '')
            app_name = self.notification.get('app_name', 'Unknown')

            # 1. Try to load the custom image file first
            if icon_path and os.path.exists(icon_path):
                try:
                    texture = Gdk.Texture.new_from_filename(icon_path)
                    self.avatar.set_custom_image(texture)
                    return
                except GLib.Error as e:
                    print(f"Failed to load texture from {icon_path}: {e}")

            # 2. For symbolic icons, just use text - Adw.Avatar will make it circular and colored
            # The avatar automatically generates nice colored backgrounds for text
            self.avatar.set_text(app_name[0].upper() if app_name else "?")

        except Exception as e:
            print(f"Error in load_icon: {e}")
            # Emergency fallback
            app_name = self.notification.get('app_name', '?')
            self.avatar.set_text(app_name[0].upper())

    def get_symbolic_icon_name(self, app_name):
        """Get appropriate symbolic icon name"""
        if 'spotify' in app_name:
            return "audio-x-generic-symbolic"
        elif any(browser in app_name for browser in ['firefox', 'chrome', 'browser', 'plasma-browser']):
            return "web-browser-symbolic"
        elif 'discord' in app_name or 'vesktop' in app_name:
            return "user-available-symbolic"
        elif any(screen in app_name for screen in ['notify-send', 'screenshot']):
            return "camera-photo-symbolic"
        else:
            return "dialog-information-symbolic"
    
    def format_timestamp(self):
        """Format timestamp"""
        timestamp_str = self.notification.get('timestamp', '')
        if not timestamp_str:
            return "Unknown"
        
        try:
            if 'T' in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.fromisoformat(timestamp_str)
            
            now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
            diff = now - timestamp
            
            if diff.total_seconds() < 60:
                return "now"
            elif diff.total_seconds() < 3600:
                mins = int(diff.total_seconds() // 60)
                return f"{mins}m ago"
            elif diff.days == 0:
                return timestamp.strftime('%H:%M')
            elif diff.days == 1:
                return "yesterday"
            else:
                return timestamp.strftime('%m/%d')
                
        except:
            return "unknown"
    
    def toggle_expanded(self):
        """Toggle expanded state"""
        if not self.body_revealer:
            return
        
        self.expanded = not self.expanded
        self.body_revealer.set_reveal_child(self.expanded)
        
        if self.expanded:
            self.expand_icon.set_from_icon_name("pan-down-symbolic")
            self.add_css_class("expanded")
        else:
            self.expand_icon.set_from_icon_name("pan-end-symbolic")
            self.remove_css_class("expanded")
    
    def matches_search(self, search_text):
        """Search matching"""
        if not search_text:
            return True
        
        search_lower = search_text.lower()
        searchable = (
            self.notification.get('app_name', '') + ' ' +
            self.notification.get('summary', '') + ' ' +
            self.notification.get('body', '')
        ).lower()
        
        return search_lower in searchable

class NotificationsWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.notifications_file = os.path.expanduser("~/.local/share/dunst/notifications.json")
        self.all_notifications = []
        self.notification_rows = []
        self.search_text = ""
        self.file_monitor = None
        self.last_modified_time = 0
        
        self.create_ui()
        self.setup_css()  # Add CSS for circular styling
        GLib.timeout_add(100, self.init_notifications)
    
    def setup_css(self):
        """Setup CSS for circular icons"""
        css_provider = Gtk.CssProvider()
        css = """
        .circular-icon {
            border-radius: 50%;
            background-color: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        """
        css_provider.load_from_data(css.encode())
        
        display = Gtk.Widget.get_default_direction()
        Gtk.StyleContext.add_provider_for_display(
            self.get_display() if hasattr(self, 'get_display') else Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def create_ui(self):
        # FIXED: Header that stays at top (not scrolled)
        header_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_top(20)
        header_box.set_margin_bottom(16)
        header_box.set_margin_start(20)
        header_box.set_margin_end(20)
        
        # Title
        title_label = Gtk.Label(label="Notifications")
        title_label.add_css_class("title-large")
        title_label.set_halign(Gtk.Align.START)
        
        # Search
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search notifications...")
        self.search_entry.set_size_request(220, -1)
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        
        # Clear button
        clear_button = Gtk.Button()
        clear_button.set_icon_name("edit-clear-all-symbolic")
        clear_button.set_tooltip_text("Clear all notifications")
        clear_button.add_css_class("circular")
        clear_button.connect("clicked", self.clear_notifications)
        
        header_box.append(title_label)
        header_box.append(self.search_entry)
        header_box.append(clear_button)
        
        # Search info
        self.search_info = Gtk.Label()
        self.search_info.set_halign(Gtk.Align.START)
        self.search_info.add_css_class("dim-label")
        self.search_info.set_margin_start(20)
        self.search_info.set_margin_bottom(8)
        self.search_info.set_visible(False)
        
        header_container.append(header_box)
        header_container.append(self.search_info)
        
        # Scrollable content area with INVISIBLE main scrollbar
        scrolled_area = Gtk.ScrolledWindow()
        scrolled_area.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_area.set_vexpand(True)
        scrolled_area.add_css_class("invisible-scroll")
        
        # Content container
        content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_container.set_margin_start(16)
        content_container.set_margin_end(16)
        content_container.set_margin_top(8)
        content_container.set_margin_bottom(16)
        
        # Notifications list
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("notifications-list")
        self.listbox.connect("row-activated", self.on_notification_clicked)
        
        content_container.append(self.listbox)
        scrolled_area.set_child(content_container)
        
        # Structure that keeps header fixed at top
        self.append(header_container)
        self.append(scrolled_area)
    
    def init_notifications(self):
        """Initialize notifications and set up file monitoring"""
        try:
            self.load_notifications()
            self.setup_file_monitor()
        except Exception as e:
            print(f"Error initializing notifications: {e}")
        return False
    
    def setup_file_monitor(self):
        """Set up file monitoring for real-time updates"""
        try:
            if not os.path.exists(self.notifications_file):
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(self.notifications_file), exist_ok=True)
                # Create empty file
                with open(self.notifications_file, 'w') as f:
                    json.dump([], f)
            
            # Set up file monitor
            file = Gio.File.new_for_path(self.notifications_file)
            self.file_monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self.file_monitor.connect("changed", self.on_file_changed)
            
            print("File monitor set up successfully")
            
        except Exception as e:
            print(f"Error setting up file monitor: {e}")
            # Fallback to periodic polling
            GLib.timeout_add_seconds(2, self.check_file_changes)
    
    def on_file_changed(self, monitor, file, other_file, event_type):
        """Handle file changes"""
        if event_type in [Gio.FileMonitorEvent.CHANGED, 
                         Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                         Gio.FileMonitorEvent.CREATED]:
            # Add a small delay to ensure the write is complete
            GLib.timeout_add(200, self.reload_notifications)
    
    def check_file_changes(self):
        """Fallback method to check for file changes periodically"""
        try:
            if os.path.exists(self.notifications_file):
                current_mtime = os.path.getmtime(self.notifications_file)
                if current_mtime > self.last_modified_time:
                    self.last_modified_time = current_mtime
                    self.reload_notifications()
        except Exception as e:
            print(f"Error checking file changes: {e}")
        return True  # Continue the timeout
    
    def reload_notifications(self):
        """Reload notifications (called by file monitor)"""
        try:
            # Store current scroll position
            scrolled_window = None
            current_scroll = 0
            
            # Find the scrolled window
            def find_scrolled_window(widget):
                nonlocal scrolled_window
                if isinstance(widget, Gtk.ScrolledWindow):
                    scrolled_window = widget
                    return
                if hasattr(widget, 'get_first_child'):
                    child = widget.get_first_child()
                    while child:
                        find_scrolled_window(child)
                        child = child.get_next_sibling()
            
            find_scrolled_window(self)
            
            if scrolled_window:
                vadj = scrolled_window.get_vadjustment()
                if vadj:
                    current_scroll = vadj.get_value()
            
            # Reload notifications
            self.load_notifications()
            
            # Restore scroll position after a brief delay
            if scrolled_window and current_scroll > 0:
                def restore_scroll():
                    vadj = scrolled_window.get_vadjustment()
                    if vadj:
                        vadj.set_value(min(current_scroll, vadj.get_upper() - vadj.get_page_size()))
                    return False
                
                GLib.timeout_add(50, restore_scroll)
                
        except Exception as e:
            print(f"Error reloading notifications: {e}")
        return False
    
    def load_notifications(self):
        """Load notifications"""
        try:
            if not os.path.exists(self.notifications_file):
                self.show_empty_state("No notifications found")
                return True
            
            # Update last modified time
            self.last_modified_time = os.path.getmtime(self.notifications_file)
            
            with open(self.notifications_file, 'r') as f:
                notifications = json.load(f)
            
            if not notifications:
                self.show_empty_state("No notifications")
                return True
            
            notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Only update if notifications actually changed
            if notifications != self.all_notifications:
                self.all_notifications = notifications
                self.create_notification_rows()
                self.filter_notifications()
            
        except Exception as e:
            print(f"Error loading notifications: {e}")
            self.show_empty_state("Error loading notifications")
        
        return True
    
    def create_notification_rows(self):
        """Create notification rows"""
        self.notification_rows = []
        for notification in self.all_notifications:
            try:
                row = NotificationRow(notification)
                self.notification_rows.append(row)
            except Exception as e:
                print(f"Error creating notification row: {e}")
    
    def on_search_changed(self, search_entry):
        """Handle search"""
        self.search_text = search_entry.get_text().strip()
        self.filter_notifications()
    
    def filter_notifications(self):
        """Filter notifications"""
        try:
            # Clear existing
            while True:
                child = self.listbox.get_first_child()
                if child is None:
                    break
                self.listbox.remove(child)
            
            if not self.notification_rows:
                self.show_empty_state("No notifications")
                return
            
            # Filter
            if self.search_text:
                filtered_rows = [row for row in self.notification_rows 
                               if row.matches_search(self.search_text)]
            else:
                filtered_rows = self.notification_rows
            
            if not filtered_rows:
                self.show_empty_state(f"No results for '{self.search_text}'" if self.search_text else "No notifications")
                self.update_search_info(0, len(self.notification_rows))
                return
            
            # Add rows
            for row in filtered_rows:
                self.listbox.append(row)
            
            self.update_search_info(len(filtered_rows), len(self.notification_rows))
            
        except Exception as e:
            print(f"Error filtering notifications: {e}")
    
    def update_search_info(self, shown, total):
        """Update search info"""
        if self.search_text and total > 0:
            self.search_info.set_text(f"Showing {shown} of {total} notifications")
            self.search_info.set_visible(True)
        else:
            self.search_info.set_visible(False)
    
    def show_empty_state(self, message):
        """Show empty state"""
        while True:
            child = self.listbox.get_first_child()
            if child is None:
                break
            self.listbox.remove(child)
        
        empty_label = Gtk.Label(label=message)
        empty_label.add_css_class("dim-label")
        empty_label.set_margin_top(50)
        empty_label.set_margin_bottom(50)
        self.listbox.append(empty_label)
    
    def on_notification_clicked(self, listbox, row):
        """Handle notification clicks"""
        try:
            if isinstance(row, NotificationRow):
                row.toggle_expanded()
        except Exception as e:
            print(f"Error handling notification click: {e}")
    
    def clear_notifications(self, button):
        """Clear notifications"""
        try:
            if os.path.exists(self.notifications_file):
                subprocess.run(['rm','-rf', '~/.local/share/dunst/images'])
                subprocess.run(['mkdir', '~/.local/share/dunst/images'])
                with open(self.notifications_file, 'w') as f:
                    json.dump([], f)
                self.search_entry.set_text("")
                # File monitor will automatically trigger reload
        except Exception as e:
            print(f"Error clearing notifications: {e}")
    
    def __del__(self):
        """Cleanup when widget is destroyed"""
        try:
            if self.file_monitor:
                self.file_monitor.cancel()
        except:
            pass