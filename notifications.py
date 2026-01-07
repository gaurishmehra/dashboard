import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gio, Gdk
import json
import os
from datetime import datetime, timezone
import warnings
import subprocess
import math
import threading

warnings.filterwarnings("ignore", category=DeprecationWarning)

class NotificationRow(Gtk.ListBoxRow):
    def __init__(self, notification, parent_widget, search_term=None):
        super().__init__()
        self.notification = notification
        self.parent_widget = parent_widget
        self.search_term = search_term
        self.expanded = False
        self.image_loaded = False
        self.image_widget = None
        self.body_revealer = None
        self.body_built = False

        self.set_activatable(True)
        self.add_css_class("notification-row")

        self.create_ui()

    def create_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header section (always visible)
        self.create_header()
        
        # Body section (expandable) - create placeholder
        self.create_expandable_body_placeholder()
        
        self.set_child(self.main_box)

    def create_header(self):
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, 
            spacing=12,
            margin_top=12, 
            margin_bottom=12, 
            margin_start=16, 
            margin_end=16
        )

        # Avatar
        self.avatar = Adw.Avatar(
            size=48, 
            halign=Gtk.Align.CENTER, 
            valign=Gtk.Align.CENTER
        )
        self.load_avatar_icon()

        # Content section
        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, 
            spacing=4,
            hexpand=True,
            valign=Gtk.Align.CENTER
        )

        # App name
        app_name_label = Gtk.Label(
            label=self.notification.get('app_name', 'System'),
            halign=Gtk.Align.START, 
            xalign=0, 
            css_classes=["app-name", "title-4"]
        )

        # Summary
        summary_text = self.notification.get('summary', 'No summary')
        summary_label = Gtk.Label(
            halign=Gtk.Align.START, 
            xalign=0, 
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=50, 
            css_classes=["summary-label", "body"]
        )
        summary_label.set_markup(self.highlight_text(summary_text, self.search_term))

        content_box.append(app_name_label)
        content_box.append(summary_label)

        # Time label
        time_label = Gtk.Label(
            label=self.format_timestamp(),
            valign=Gtk.Align.CENTER,
            margin_end=6,
            css_classes=["time-label", "caption"]
        )

        # Expand icon (only if there's body content or image)
        body_text = self.notification.get('body', '').strip()
        icon_path = self.notification.get('icon', '')
        has_expandable_content = bool(body_text or (icon_path and os.path.exists(icon_path)))
        
        if has_expandable_content:
            self.expand_icon = Gtk.Image(
                icon_name="pan-end-symbolic", 
                css_classes=["expand-icon"], 
                valign=Gtk.Align.CENTER
            )
            header_box.append(self.avatar)
            header_box.append(content_box)
            header_box.append(time_label)
            header_box.append(self.expand_icon)
        else:
            self.expand_icon = None
            header_box.append(self.avatar)
            header_box.append(content_box)
            header_box.append(time_label)

        self.main_box.append(header_box)

    def create_expandable_body_placeholder(self):
        body_text = self.notification.get('body', '').strip()
        icon_path = self.notification.get('icon', '')
        has_image = icon_path and os.path.exists(icon_path)
        
        if not body_text and not has_image:
            self.body_revealer = None
            return

        # Create revealer for smooth animation
        self.body_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=150,
            reveal_child=False
        )
        self.main_box.append(self.body_revealer)

    def build_expandable_body(self):
        if self.body_built:
            return

        # Main expanded content container
        expanded_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=76,  # Align with content, accounting for avatar
            margin_end=16,
            margin_bottom=20,
            css_classes=["expanded-content"]
        )

        # Add body text section first (give it priority)
        body_text = self.notification.get('body', '').strip()
        if body_text:
            self.create_body_section(expanded_container, body_text)

        # Add image section after text
        icon_path = self.notification.get('icon', '')
        has_image = icon_path and os.path.exists(icon_path)
        if has_image:
            self.create_image_section(expanded_container)

        # Add action buttons section
        self.create_action_section(expanded_container)

        self.body_revealer.set_child(expanded_container)
        self.body_built = True

    def create_image_section(self, container):
        # Image container with proper styling
        image_frame = Gtk.Frame(css_classes=["notification-image-frame"])
        image_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
            margin_bottom=8,
            margin_start=8,
            margin_end=8
        )

        # Placeholder for image (will be loaded when expanded)
        self.image_widget = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            height_request=100
        )

        # Loading placeholder
        self.image_spinner = Gtk.Spinner()
        loading_label = Gtk.Label(
            label="Loading image...",
            css_classes=["dim-label", "caption"]
        )
        
        self.image_widget.append(self.image_spinner)
        self.image_widget.append(loading_label)

        image_container.append(self.image_widget)
        image_frame.set_child(image_container)
        container.append(image_frame)

    def create_body_section(self, container, body_text):
        # Body text container - much more generous with space
        body_frame = Gtk.Frame(css_classes=["notification-body-frame"])

        # Body text with much better space allocation
        body_label = Gtk.Label(
            halign=Gtk.Align.START,
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            selectable=True,
            css_classes=["notification-body-text"]
        )
        body_label.set_markup(self.highlight_text(body_text, self.search_term))

        # Add padding
        body_label.set_margin_top(12)
        body_label.set_margin_bottom(12)
        body_label.set_margin_start(12)
        body_label.set_margin_end(12)

        # More generous height limits and better scrolling behavior
        lines_count = len(body_text.splitlines())
        char_count = len(body_text)
        
        # Determine if we need scrolling - more lenient criteria
        needs_scrolling = lines_count > 15 or char_count > 1000
        
        if needs_scrolling:
            scrolled_body = Gtk.ScrolledWindow(
                css_classes=["notification-body-scroll"],
                hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                min_content_height=200,  # Minimum height
                max_content_height=400,  # Much more generous max height
                propagate_natural_height=True,
                vexpand=True  # Allow it to expand vertically
            )
            scrolled_body.set_child(body_label)
            body_frame.set_child(scrolled_body)
        else:
            # For shorter text, just let it expand naturally
            body_label.set_vexpand(True)
            body_frame.set_child(body_label)

        container.append(body_frame)

    def create_action_section(self, container):
        # Action buttons
        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            css_classes=["notification-actions"]
        )

        # Copy button for body text
        body_text = self.notification.get('body', '').strip()
        if body_text:
            copy_button = Gtk.Button(
                label="Copy Text",
                css_classes=["pill"]
            )
            copy_button.connect("clicked", self.on_copy_text_clicked)
            action_box.append(copy_button)

        # Open image button (if image exists)
        icon_path = self.notification.get('icon', '')
        if icon_path and os.path.exists(icon_path):
            open_image_button = Gtk.Button(
                label="Open Image",
                css_classes=["pill"]
            )
            open_image_button.connect("clicked", self.on_open_image_clicked)
            action_box.append(open_image_button)

        if action_box.get_first_child():  # Only add if there are buttons
            container.append(action_box)

    def highlight_text(self, text, search_term):
        """Highlights search_term in text using Pango markup, case-insensitively."""
        if not search_term or not text:
            return GLib.markup_escape_text(text)
        
        try:
            import re
            escaped_text = GLib.markup_escape_text(text)
            escaped_search = re.escape(search_term)
            highlight_format = "<span background='#FFFF004D' font_weight='bold'>\\g<0></span>"
            highlighted_text = re.sub(f'({escaped_search})', highlight_format, escaped_text, flags=re.IGNORECASE)
            return highlighted_text
        except Exception:
            return GLib.markup_escape_text(text)

    def load_avatar_icon(self):
        """Load the avatar icon for the notification header"""
        icon_path = self.notification.get('icon', '')
        app_name = self.notification.get('app_name', 'System')

        if icon_path and os.path.exists(icon_path):
            try:
                texture = Gdk.Texture.new_from_filename(icon_path)
                self.avatar.set_custom_image(texture)
                return
            except GLib.Error:
                pass  # Fall back to text avatar

        self.avatar.set_text(app_name[0].upper() if app_name else "S")

    def load_notification_image_async(self):
        """Lazy load the full notification image when expanded"""
        if self.image_loaded or not self.image_widget:
            return

        if hasattr(self, 'image_spinner'):
            self.image_spinner.start()
        
        thread = threading.Thread(target=self.load_image_worker, daemon=True)
        thread.start()

    def load_image_worker(self):
        """Worker thread for loading image"""
        icon_path = self.notification.get('icon', '')
        if not icon_path or not os.path.exists(icon_path):
            GLib.idle_add(self.update_image_ui_error, "File not found")
            return

        try:
            texture = Gdk.Texture.new_from_filename(icon_path)
            GLib.idle_add(self.update_image_ui_success, texture)
        except Exception as e:
            GLib.idle_add(self.update_image_ui_error, str(e))

    def update_image_ui_success(self, texture):
        """Update image UI with loaded texture"""
        try:
            # Calculate appropriate size - more generous for images
            original_width = texture.get_width()
            original_height = texture.get_height()
            
            # Allow larger images, but still reasonable
            max_width = 400
            max_height = 300
            
            scale_factor = min(max_width / original_width, max_height / original_height, 1.0)
            display_width = int(original_width * scale_factor)
            display_height = int(original_height * scale_factor)

            # Clear loading placeholder
            while self.image_widget.get_first_child():
                self.image_widget.remove(self.image_widget.get_first_child())

            # Create image widget
            image_widget = Gtk.Picture()
            image_widget.set_paintable(texture)
            image_widget.set_size_request(display_width, display_height)
            image_widget.set_can_shrink(True)
            image_widget.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
            image_widget.add_css_class("notification-image")

            # Image info label
            size_text = f"{original_width}×{original_height} pixels"
            info_label = Gtk.Label(
                label=size_text,
                css_classes=["dim-label", "caption"],
                halign=Gtk.Align.CENTER
            )

            self.image_widget.append(image_widget)
            self.image_widget.append(info_label)
            
            self.image_loaded = True

        except Exception as e:
            self.update_image_ui_error(str(e))

        return GLib.SOURCE_REMOVE

    def update_image_ui_error(self, error_msg):
        """Update image UI with error state"""
        # Clear loading placeholder
        while self.image_widget.get_first_child():
            self.image_widget.remove(self.image_widget.get_first_child())
        
        error_icon = Gtk.Image(
            icon_name="image-missing-symbolic",
            pixel_size=48,
            css_classes=["dim-label"]
        )
        error_label = Gtk.Label(
            label="Failed to load image",
            css_classes=["dim-label", "caption"]
        )
        
        self.image_widget.append(error_icon)
        self.image_widget.append(error_label)
        print(f"Error loading notification image: {error_msg}")
        
        return GLib.SOURCE_REMOVE

    def format_timestamp(self):
        ts_str = self.notification.get('timestamp', '')
        if not ts_str:
            return "just now"

        try:
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except ValueError:
                ts = datetime.fromisoformat(ts_str)

            if ts.tzinfo is None:
                ts = ts.astimezone()

            now = datetime.now(ts.tzinfo)
            diff = now - ts

            seconds = diff.total_seconds()
            if seconds < 60:
                return "now"
            elif seconds < 3600:
                return f"{int(seconds // 60)}m ago"
            elif diff.days == 0:
                return ts.strftime('%H:%M')
            elif diff.days == 1:
                return "yesterday"
            else:
                return ts.strftime('%b %d')
        except (ValueError, TypeError) as e:
            print(f"Could not parse timestamp '{ts_str}': {e}")
            return "unknown"

    def toggle_expanded(self):
        if not self.body_revealer:
            return

        self.expanded = not self.expanded
        self.build_expandable_body()  # Build content sync (fast)
        self.body_revealer.set_reveal_child(self.expanded)

        if self.expanded:
            if self.expand_icon:
                self.expand_icon.set_from_icon_name("pan-up-symbolic")
            self.add_css_class("expanded")
            
            # Load image when expanding
            GLib.timeout_add(100, self.load_notification_image_async)
        else:
            if self.expand_icon:
                self.expand_icon.set_from_icon_name("pan-end-symbolic")
            self.remove_css_class("expanded")

    def on_copy_text_clicked(self, button):
        """Copy notification text to clipboard"""
        body_text = self.notification.get('body', '').strip()
        if body_text:
            clipboard = Gdk.Display.get_default().get_clipboard()
            clipboard.set(body_text)
            
            # Visual feedback
            original_label = button.get_label()
            button.set_label("Copied!")
            button.set_sensitive(False)
            
            def reset_button():
                button.set_label(original_label)
                button.set_sensitive(True)
                return False
            
            GLib.timeout_add(1500, reset_button)
            
            # Show toast if available
            if hasattr(self.parent_widget, 'show_toast'):
                self.parent_widget.show_toast("Copied to clipboard!")

    def on_open_image_clicked(self, button):
        """Open image in default application"""
        icon_path = self.notification.get('icon', '')
        if icon_path and os.path.exists(icon_path):
            try:
                subprocess.run(['xdg-open', icon_path], check=False)
            except Exception as e:
                print(f"Error opening image: {e}")

    def cleanup(self):
        """Clean up resources when row is removed"""
        self.image_loaded = False
        if self.image_widget:
            while self.image_widget.get_first_child():
                self.image_widget.remove(self.image_widget.get_first_child())


class NotificationsWidget(Gtk.Box):
    def __init__(self, toast_overlay=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.toast_overlay = toast_overlay
        self.notifications_file = os.path.expanduser("~/.local/share/dunst/notifications.json")
        self.all_notifications = []
        self.visible_rows = []  # Track currently visible rows

        self.file_monitor = None
        self.last_mtime = 0
        self.is_active = False

        # Pagination state
        self.current_page = 0
        self.items_per_page = 10
        self.total_pages = 0
        self.search_timeout_id = 0

        # Lazy UI creation
        self.ui_built = False

    def activate(self):
        if self.is_active:
            return

        if not self.ui_built:
            self.create_ui()
            self.ui_built = True

        self.is_active = True
        print("NotificationsWidget Activated")
        self.reload_notifications()
        self.setup_file_monitor()

    def deactivate(self):
        if not self.is_active:
            return
        self.is_active = False
        print("NotificationsWidget Deactivated")
        
        # Clean up visible rows
        self.cleanup_visible_rows()
        
        if self.file_monitor:
            self.file_monitor.cancel()
            self.file_monitor = None

        if self.search_timeout_id > 0:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = 0

    def cleanup_visible_rows(self):
        """Clean up resources from currently visible rows"""
        for row in self.visible_rows:
            if hasattr(row, 'cleanup'):
                row.cleanup()
        self.visible_rows.clear()

    def create_ui(self):
        # Header
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, 
            spacing=12,
            margin_top=16, 
            margin_bottom=12, 
            margin_start=20, 
            margin_end=20
        )

        title_label = Gtk.Label(
            label="Notifications", 
            halign=Gtk.Align.START, 
            css_classes=["title-large"]
        )
        header_box.append(title_label)

        self.search_entry = Gtk.SearchEntry(
            placeholder_text="Search notifications...", 
            hexpand=True,
            margin_start=12
        )
        self.search_entry.connect("search-changed", self.on_search_changed_debounced)
        header_box.append(self.search_entry)

        clear_button = Gtk.Button(
            icon_name="edit-clear-all-symbolic", 
            tooltip_text="Clear History", 
            css_classes=["circular"],
            margin_start=12
        )
        clear_button.connect("clicked", self.on_clear_clicked)
        header_box.append(clear_button)

        # Content stack for loading/content states
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_vexpand(True)

        # Loading page
        loading_page = self.create_loading_page()
        self.content_stack.add_named(loading_page, "loading")

        # Scrolled area for notifications - make it more generous
        scrolled_area = Gtk.ScrolledWindow(
            vexpand=True, 
            css_classes=["invisible-scroll"],
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True
        )

        self.listbox = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["notifications-list"],
            margin_start=16, 
            margin_end=16, 
            margin_bottom=8
        )
        self.listbox.connect("row-activated", lambda lb, row: row.toggle_expanded())

        scrolled_area.set_child(self.listbox)
        self.content_stack.add_named(scrolled_area, "content")
        
        # Footer for pagination
        footer_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_start=20, 
            margin_end=20, 
            margin_bottom=16
        )

        # Stats section
        stats_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2
        )
        self.stats_label = Gtk.Label(
            halign=Gtk.Align.START, 
            css_classes=["dim-label"]
        )
        self.page_info_label = Gtk.Label(
            halign=Gtk.Align.START, 
            css_classes=["dim-label"]
        )
        stats_box.append(self.stats_label)
        stats_box.append(self.page_info_label)
        footer_box.append(stats_box)

        page_controls_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, 
            spacing=6,
            halign=Gtk.Align.END, 
            hexpand=True
        )
        
        self.prev_button = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.prev_button.set_tooltip_text("Previous page")
        self.prev_button.connect("clicked", self.on_prev_page_clicked)

        self.next_button = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self.next_button.set_tooltip_text("Next page")
        self.next_button.connect("clicked", self.on_next_page_clicked)

        page_controls_box.append(self.prev_button)
        page_controls_box.append(self.next_button)
        footer_box.append(page_controls_box)

        # Add keyboard shortcuts
        self.add_keyboard_shortcuts()

        # Add all sections to main widget
        self.append(header_box)
        self.append(self.content_stack)
        self.append(footer_box)

    def create_loading_page(self):
        """Creates the loading spinner page."""
        spinner = Gtk.Spinner()
        spinner.start()
        status_page = Adw.StatusPage.new()
        status_page.set_title("Loading Notifications")
        status_page.set_child(spinner)
        status_page.set_vexpand(True)
        return status_page

    def add_keyboard_shortcuts(self):
        # Window-level shortcuts
        win_key_controller = Gtk.EventControllerKey()
        win_key_controller.connect("key-pressed", self.on_win_key_pressed)
        self.add_controller(win_key_controller)

    def on_win_key_pressed(self, controller, keyval, keycode, state):
        if self.search_entry.has_focus(): 
            return False
        
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up) and self.prev_button.get_sensitive():
            self.on_prev_page_clicked(None)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down) and self.next_button.get_sensitive():
            self.on_next_page_clicked(None)
            return True
        elif keyval == Gdk.KEY_F5:
            self.reload_notifications()
            return True
        return False

    def setup_file_monitor(self):
        if self.file_monitor:
            return
        try:
            notif_dir = os.path.dirname(self.notifications_file)
            if not os.path.exists(notif_dir):
                os.makedirs(notif_dir, exist_ok=True)
            if not os.path.exists(self.notifications_file):
                with open(self.notifications_file, 'w') as f:
                    json.dump([], f)

            file = Gio.File.new_for_path(self.notifications_file)
            self.file_monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self.file_monitor.connect("changed", lambda *args: GLib.timeout_add(500, self.reload_notifications))
            print("File monitor started for notifications.")
        except Exception as e:
            print(f"Failed to set up file monitor: {e}")

    def reload_notifications(self):
        if not self.is_active:
            return GLib.SOURCE_REMOVE

        try:
            if not os.path.exists(self.notifications_file):
                self.all_notifications = []
                self.last_mtime = 0
            else:
                current_mtime = os.path.getmtime(self.notifications_file)
                if current_mtime == self.last_mtime:
                    return GLib.SOURCE_REMOVE

                self.last_mtime = current_mtime
                with open(self.notifications_file, 'r') as f:
                    content = f.read()
                    self.all_notifications = json.loads(content) if content else []

            self.all_notifications.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Reset to first page on full reload
            self.current_page = 0
            self.filter_notifications()

        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading notifications file: {e}")
            self.all_notifications = []
            self.filter_notifications()

        # Show content after loading
        if hasattr(self, 'content_stack'):
            self.content_stack.set_visible_child_name("content")

        return GLib.SOURCE_REMOVE

    def notification_matches_search(self, notification, search_text):
        if not search_text:
            return True

        search_lower = search_text.lower()
        content = (
            notification.get('app_name', '') + ' ' +
            notification.get('summary', '') + ' ' +
            notification.get('body', '')
        ).lower()

        return search_lower in content

    def on_search_changed_debounced(self, entry):
        if self.search_timeout_id > 0: 
            GLib.source_remove(self.search_timeout_id)
        self.search_timeout_id = GLib.timeout_add(300, self.on_search_changed)

    def on_search_changed(self, *args):
        self.current_page = 0
        self.filter_notifications()
        return GLib.SOURCE_REMOVE

    def on_prev_page_clicked(self, button):
        if self.current_page > 0:
            self.current_page -= 1
            self.filter_notifications()

    def on_next_page_clicked(self, button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.filter_notifications()
            
    def filter_notifications(self):
        search_text = self.search_entry.get_text().strip()

        # Get filtered notifications
        filtered_notifications = [n for n in self.all_notifications if self.notification_matches_search(n, search_text)]
        total_items = len(filtered_notifications)

        # Clean up previous visible rows
        self.cleanup_visible_rows()

        # Clear listbox
        child = self.listbox.get_first_child()
        while child:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()

        # Handle empty state
        if total_items == 0:
            if search_text:
                self.show_placeholder(f"No results for '{search_text}'", "edit-find-symbolic")
            else:
                self.show_placeholder("No notifications yet.", "notification-symbolic")
            self.update_page_controls(0)
            return

        # Calculate pagination
        self.total_pages = math.ceil(total_items / self.items_per_page)
        self.current_page = max(0, min(self.current_page, self.total_pages - 1))
            
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        
        # Get notifications for current page only
        page_notifications = filtered_notifications[start_index:end_index]

        # Create rows only for current page
        rows_for_current_page = [NotificationRow(n, self, search_text if search_text else None) for n in page_notifications]

        # Add only current page rows to listbox and track them
        self.visible_rows = rows_for_current_page[:]
        for row in rows_for_current_page:
            self.listbox.append(row)

        self.update_page_controls(total_items)

    def update_page_controls(self, total_items):
        footer_box = self.stats_label.get_parent().get_parent()
        
        if total_items == 0 or self.total_pages <= 1:
            footer_box.set_visible(False)
            return
        
        footer_box.set_visible(True)

        # Update stats
        self.stats_label.set_text(f"{total_items} notification{'s' if total_items != 1 else ''}")
        
        # Update page info
        page_str = f"Page {self.current_page + 1} of {self.total_pages}"
        self.page_info_label.set_text(page_str)
        
        # Update button states
        self.prev_button.set_sensitive(self.current_page > 0)
        self.next_button.set_sensitive(self.current_page < self.total_pages - 1)
        
    def show_placeholder(self, text, icon_name):
        placeholder_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, 
            spacing=12,
            margin_top=40, 
            margin_bottom=40,
            vexpand=True,
            hexpand=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        
        label = Gtk.Label(
            label=text, 
            css_classes=["dim-label"],
            justify=Gtk.Justification.CENTER
        )
        
        placeholder_box.append(icon)
        placeholder_box.append(label)
        
        placeholder_row = Gtk.ListBoxRow(
            selectable=False,
            activatable=False
        )
        placeholder_row.set_child(placeholder_box)
        
        self.listbox.append(placeholder_row)

    def on_clear_clicked(self, button):
        dialog = Adw.MessageDialog.new(
            self.get_root(), 
            "Clear Notification History?",
            "This will permanently delete all notification history."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear All")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_clear_dialog_response)
        dialog.present()

    def on_clear_dialog_response(self, dialog, response):
        if response == "clear":
            try:
                with open(self.notifications_file, 'w') as f:
                    json.dump([], f)

                images_dir = os.path.expanduser("~/.local/share/dunst/images")
                if os.path.exists(images_dir):
                    subprocess.run(['rm', '-rf', f'{images_dir}/*'], shell=True, check=False)

                self.search_entry.set_text("")
                print("Notification history cleared.")
                self.reload_notifications()
                self.show_toast("Notification history cleared.")

            except Exception as e:
                print(f"Error clearing notifications: {e}")
                self.show_toast("Error: Failed to clear history.")
        
        dialog.close()

    def show_toast(self, text):
        """Show a toast notification"""
        if self.toast_overlay:
            self.toast_overlay.add_toast(Adw.Toast.new(text))