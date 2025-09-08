import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk, Pango
import subprocess
import os
import math
import re
import threading

# A Note on Dependencies:
# This widget requires 'cliphist' and 'wl-clipboard' to be installed on your system.
# It uses 'cliphist' for history management and 'wl-copy' for copying items.

def highlight_text(text, search_term):
    """Highlights search_term in text using Pango markup, case-insensitively."""
    if not search_term or not text:
        return GLib.markup_escape_text(text)
    
    try:
        escaped_text = GLib.markup_escape_text(text)
        escaped_search = re.escape(search_term)
        highlight_format = "<span background='#FFFF004D' font_weight='bold'>\\g<0></span>"
        highlighted_text = re.sub(f'({escaped_search})', highlight_format, escaped_text, flags=re.IGNORECASE)
        return highlighted_text
    except Exception:
        return GLib.markup_escape_text(text)

def get_full_clipboard_content(item_text):
    """Decodes the full clipboard content from a cliphist list item."""
    try:
        process = subprocess.Popen(['cliphist', 'decode'], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(input=item_text.encode('utf-8'))
        if process.returncode != 0:
            print(f"cliphist decode error: {stderr.decode()}")
            return None
        return stdout.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error getting full content: {e}")
        return None

def get_clipboard_bytes(item_text):
    """Decodes the full clipboard bytes from a cliphist list item."""
    try:
        process = subprocess.Popen(['cliphist', 'decode'], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(input=item_text.encode('utf-8'))
        if process.returncode != 0:
            print(f"cliphist decode error: {stderr.decode()}")
            return None
        return stdout
    except Exception as e:
        print(f"Error getting full bytes: {e}")
        return None

def is_image_item(item_text: str) -> bool:
    item_content = item_text.split('\t', 1)[-1]
    return ('[i]' in item_text) or item_content.strip().startswith('[[ binary data')

def preview_text_of(item_text: str) -> str:
    preview = item_text.split('\t', 1)[-1].strip()
    preview = re.sub(r'\s+', ' ', preview).strip()
    return preview

# Represents a single, expandable item in the clipboard history.
class ClipboardRow(Gtk.ListBoxRow):
    def __init__(self, item_text, parent_widget, search_term=None):
        super().__init__()
        
        self.add_css_class("notification-row")
        self.item_text = item_text
        self.parent_widget = parent_widget
        self.search_term = search_term
        self.full_content = None
        self.is_image = is_image_item(self.item_text)
        self.expanded = False
        self.content_loaded = False
        self.image_widget = None
        self.text_scrolled = None
        self.text_placeholder = None
        self.image_spinner = None
        self.text_spinner = None
        self.body_revealer = None
        self.body_built = False

        self.set_activatable(True)
        self.create_ui()

    def create_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.create_header()
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
            label="Clipboard",
            halign=Gtk.Align.START, 
            xalign=0, 
            css_classes=["app-name", "title-4"]
        )

        # Summary
        summary_text = "Image" if self.is_image else preview_text_of(self.item_text)
        summary_label = Gtk.Label(
            halign=Gtk.Align.START, 
            xalign=0, 
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=50, 
            css_classes=["summary-label", "body"]
        )
        summary_label.set_markup(highlight_text(summary_text, self.search_term))

        content_box.append(app_name_label)
        content_box.append(summary_label)

        # Expand icon (always expandable)
        self.expand_icon = Gtk.Image(
            icon_name="pan-end-symbolic", 
            css_classes=["expand-icon"], 
            valign=Gtk.Align.CENTER
        )
        header_box.append(self.avatar)
        header_box.append(content_box)
        header_box.append(self.expand_icon)

        self.main_box.append(header_box)

    def create_expandable_body_placeholder(self):
        self.body_revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=300,
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

        if not self.is_image:
            self.create_text_placeholder_section(expanded_container)
        else:
            self.create_image_placeholder_section(expanded_container)

        self.create_action_section(expanded_container)

        self.body_revealer.set_child(expanded_container)
        self.body_built = True

    def create_image_placeholder_section(self, container):
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

        # Placeholder for image
        self.image_widget = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            height_request=100
        )

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

    def create_text_placeholder_section(self, container):
        # Keep only the outer frame; put the scroller directly inside it
        body_frame = Gtk.Frame(css_classes=["notification-body-frame"])

        # Allow horizontal scrolling to avoid breaking single long lines
        self.text_scrolled = Gtk.ScrolledWindow(
            css_classes=["notification-body-scroll"],
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            min_content_height=200,
            max_content_height=400,
            propagate_natural_height=True,
            vexpand=True
        )

        # Placeholder while loading
        self.text_placeholder = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            height_request=100
        )
        self.text_spinner = Gtk.Spinner()
        loading_label = Gtk.Label(
            label="Loading content...",
            css_classes=["dim-label", "caption"]
        )
        self.text_placeholder.append(self.text_spinner)
        self.text_placeholder.append(loading_label)

        self.text_scrolled.set_child(self.text_placeholder)
        body_frame.set_child(self.text_scrolled)
        container.append(body_frame)


    def create_action_section(self, container):
        # Action buttons
        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            css_classes=["notification-actions"]
        )

        copy_button = Gtk.Button(
            label="Copy",
            css_classes=["pill"]
        )
        copy_button.connect("clicked", self.on_copy_clicked)
        action_box.append(copy_button)

        delete_button = Gtk.Button(
            label="Delete",
            css_classes=["pill"]
        )
        delete_button.connect("clicked", self.on_delete_clicked)
        action_box.append(delete_button)

        container.append(action_box)

    def load_avatar_icon(self):
        icon_name = "image-x-generic-symbolic" if self.is_image else "edit-paste-symbolic"
        self.avatar.set_icon_name(icon_name)

    def load_content_async(self):
        if self.content_loaded:
            return

        if self.is_image:
            self.image_spinner.start()
            thread = threading.Thread(target=self.load_image_worker)
            thread.start()
        else:
            self.text_spinner.start()
            thread = threading.Thread(target=self.load_text_worker)
            thread.start()

    def load_image_worker(self):
        bytes_data = get_clipboard_bytes(self.item_text)
        GLib.idle_add(self.update_image_ui, bytes_data)

    def update_image_ui(self, bytes_data):
        try:
            if bytes_data is None:
                raise Exception("No bytes data")

            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(bytes_data))
            
            # Calculate appropriate size
            original_width = texture.get_width()
            original_height = texture.get_height()
            max_width = 400
            max_height = 300
            scale_factor = min(max_width / original_width, max_height / original_height, 1.0)
            display_width = int(original_width * scale_factor)
            display_height = int(original_height * scale_factor)

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

            # Clear placeholder
            while self.image_widget.get_first_child():
                self.image_widget.remove(self.image_widget.get_first_child())

            self.image_widget.append(image_widget)
            self.image_widget.append(info_label)
            
            self.content_loaded = True

        except Exception as e:
            # Show error state
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
            print(f"Error loading clipboard image: {e}")

        return GLib.SOURCE_REMOVE

    def load_text_worker(self):
        body_text = self.parent_widget.get_full_content_for_item(self.item_text) or preview_text_of(self.item_text)
        GLib.idle_add(self.update_text_ui, body_text)

# Replace your update_text_ui with this
    def update_text_ui(self, body_text):
        try:
            body_label = Gtk.Label(
                halign=Gtk.Align.START,
                xalign=0,
                selectable=True,
                css_classes=["notification-body-text"]
            )
            # Do not wrap; keep single lines single, use horizontal scroll if needed
            body_label.set_wrap(False)
            body_label.set_ellipsize(Pango.EllipsizeMode.NONE)

            # Add padding so there is only one visible box (the frame), with inner padding
            body_label.set_margin_top(12)
            body_label.set_margin_bottom(12)
            body_label.set_margin_start(12)
            body_label.set_margin_end(12)

            body_label.set_markup(highlight_text(body_text, self.search_term))

            # Replace placeholder directly (Gtk.ScrolledWindow has no remove() in GTK 4)
            self.text_scrolled.set_child(body_label)
            self.content_loaded = True

        except Exception as e:
            error_label = Gtk.Label(
                label="Failed to load content",
                css_classes=["dim-label", "caption"]
            )
            error_label.set_margin_top(12)
            error_label.set_margin_bottom(12)
            error_label.set_margin_start(12)
            error_label.set_margin_end(12)
            self.text_scrolled.set_child(error_label)
            print(f"Error loading text content: {e}")

        return GLib.SOURCE_REMOVE

    def toggle_expanded(self):
        if not self.body_revealer:
            return

        self.expanded = not self.expanded
        self.build_expandable_body()  # Build placeholders sync (fast)

        self.body_revealer.set_reveal_child(self.expanded)

        if self.expanded:
            if self.expand_icon:
                self.expand_icon.set_from_icon_name("pan-up-symbolic")
            self.add_css_class("expanded")
            
            # Start loading content async
            self.load_content_async()
        else:
            if self.expand_icon:
                self.expand_icon.set_from_icon_name("pan-end-symbolic")
            self.remove_css_class("expanded")

    def on_copy_clicked(self, button):
        try:
            process = subprocess.Popen(['cliphist', 'decode'], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = process.communicate(input=self.item_text.encode('utf-8'))
            if process.returncode == 0:
                copy_process = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE)
                copy_process.communicate(input=stdout)
                self.parent_widget.show_toast("Copied to clipboard!")
        except Exception as e:
            print(f"Error copying item: {e}")
            self.parent_widget.show_toast("Error: Failed to copy")

    def on_delete_clicked(self, button):
        self.add_css_class("deleting")
        GLib.timeout_add(300, self.perform_delete)

    def perform_delete(self):
        try:
            subprocess.run(['cliphist', 'delete'], input=self.item_text.encode('utf-8'), check=True)
        except Exception as e:
            print(f"Error deleting item: {e}")
        finally:
            self.parent_widget.load_history() # Trigger a refresh
        return GLib.SOURCE_REMOVE

    def cleanup(self):
        """Clean up resources when row is removed"""
        self.content_loaded = False
        if self.image_widget:
            while self.image_widget.get_first_child():
                self.image_widget.remove(self.image_widget.get_first_child())
        if self.text_scrolled:
            # Clear the scroller's child; ScrolledWindow has no remove() in GTK 4
            self.text_scrolled.set_child(None)

# The main widget for the clipboard history panel.
class ClipboardWidget(Gtk.Box):
    def __init__(self, toast_overlay=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay = toast_overlay
        self.all_items = []
        self.full_content_cache = {}
        self.is_active = False
        self.is_loading = False
        self.history_monitor_id = 0
        self.current_filter_mode = "all"
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = 0
        self.search_timeout_id = 0
        self.visible_rows = []
        # Lazy UI creation
        self.ui_built = False

        # Incremental search state (search is done one page at a time)
        self.search_state = None  # dict with keys: term, type_filtered, results, scan_index, fully_scanned, scan_source_id

    def activate(self):
        if self.is_active: return

        if not self.ui_built:
            self.create_ui()
            self.ui_built = True

        self.is_active = True
        self.load_history(is_initial_load=True)
        self.history_monitor_id = GLib.timeout_add_seconds(5, self.load_history, False)

    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        if self.history_monitor_id > 0:
            GLib.source_remove(self.history_monitor_id)
            self.history_monitor_id = 0
        if self.search_timeout_id > 0:
            GLib.source_remove(self.search_timeout_id)
            self.search_timeout_id = 0
        # Cancel in-progress incremental search
        self._cancel_search_scan()
        self.cleanup_visible_rows()

    def cleanup_visible_rows(self):
        for row in self.visible_rows:
            row.cleanup()
        self.visible_rows.clear()

    def create_ui(self):
        """Builds the entire UI and is only called once."""
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                             margin_top=16, margin_bottom=12, margin_start=20, margin_end=20)
        title_label = Gtk.Label(label="Clipboard History", halign=Gtk.Align.START, css_classes=["title-large"])
        header_box.append(title_label)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search history...", hexpand=True, margin_start=12)
        self.search_entry.connect("search-changed", self.on_search_changed_debounced)
        header_box.append(self.search_entry)

        filter_box = Gtk.Box(spacing=0, css_classes=["linked"], margin_start=12)
        self.all_button = Gtk.ToggleButton(label="All", active=True)
        self.text_button = Gtk.ToggleButton(label="Text", group=self.all_button)
        self.image_button = Gtk.ToggleButton(label="Images", group=self.all_button)
        self.all_button.connect("toggled", self.on_filter_toggled, "all")
        self.text_button.connect("toggled", self.on_filter_toggled, "text")
        self.image_button.connect("toggled", self.on_filter_toggled, "image")
        filter_box.append(self.all_button)
        filter_box.append(self.text_button)
        filter_box.append(self.image_button)
        header_box.append(filter_box)

        clear_button = Gtk.Button.new_from_icon_name("edit-clear-all-symbolic")
        clear_button.set_tooltip_text("Clear History")
        clear_button.add_css_class("circular")
        clear_button.set_margin_start(12)
        clear_button.connect("clicked", self.on_clear_clicked)
        header_box.append(clear_button)

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_vexpand(True)

        loading_page = self.create_loading_page()
        self.content_stack.add_named(loading_page, "loading")

        scrolled_area = Gtk.ScrolledWindow(vexpand=True, css_classes=["invisible-scroll"])
        scrolled_area.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["notifications-list"],
                                   margin_start=16, margin_end=16, margin_bottom=8)
        scrolled_area.set_child(self.listbox)
        self.listbox.connect("row-activated", lambda lb, row: row.toggle_expanded())
        self.content_stack.add_named(scrolled_area, "content")

        footer_box = Gtk.Box(margin_start=20, margin_end=20, margin_bottom=16)
        stats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.stats_label = Gtk.Label(halign=Gtk.Align.START, css_classes=["dim-label"])
        self.page_info_label = Gtk.Label(halign=Gtk.Align.START, css_classes=["dim-label"])
        stats_box.append(self.stats_label)
        stats_box.append(self.page_info_label)
        footer_box.append(stats_box)
        page_controls_box = Gtk.Box(spacing=6, halign=Gtk.Align.END, hexpand=True)
        self.prev_button = Gtk.Button.new_from_icon_name("go-previous-symbolic")
        self.prev_button.set_tooltip_text("Previous page (Left Arrow)")
        self.prev_button.connect("clicked", self.on_prev_page_clicked)
        self.next_button = Gtk.Button.new_from_icon_name("go-next-symbolic")
        self.next_button.set_tooltip_text("Next page (Right Arrow)")
        self.next_button.connect("clicked", self.on_next_page_clicked)
        page_controls_box.append(self.prev_button)
        page_controls_box.append(self.next_button)
        footer_box.append(page_controls_box)

        self.add_keyboard_shortcuts()
        self.append(header_box)
        self.append(self.content_stack)
        self.append(footer_box)

    def create_loading_page(self):
        """Creates the loading spinner page."""
        spinner = Gtk.Spinner()
        spinner.start()
        status_page = Adw.StatusPage.new()
        status_page.set_title("Loading History")
        status_page.set_child(spinner)
        status_page.set_vexpand(True)
        return status_page

    def load_history(self, is_initial_load=False):
        """Starts the clipboard history loading process in a background thread."""
        if self.is_loading:
            return True 
        
        self.is_loading = True
        if is_initial_load:
            self.content_stack.set_visible_child_name("loading")

        thread = threading.Thread(target=self._load_history_thread, args=(is_initial_load,))
        thread.daemon = True
        thread.start()
        return True

    def _load_history_thread(self, is_initial_load):
        """[Worker Thread] Fetches the history from cliphist."""
        new_items = []
        error = None
        try:
            result = subprocess.run(['cliphist', 'list'], capture_output=True, text=True, check=True)
            new_items = result.stdout.strip().split('\n') if result.stdout.strip() else []
        except Exception as e:
            error = e
        
        GLib.idle_add(self._on_history_loaded, new_items, error, is_initial_load)

    def _on_history_loaded(self, new_items, error, is_initial_load):
        """[Main Thread] Callback that updates the UI after history is loaded."""
        self.is_loading = False

        if error:
            if isinstance(error, FileNotFoundError):
                self.show_placeholder("Error: `cliphist` not found.", "dialog-error-symbolic")
            else:
                self.show_placeholder(f"Error loading history:\n{str(error)}", "dialog-error-symbolic")
            self.all_items = []
        else:
            if new_items != self.all_items or is_initial_load:
                self.all_items = new_items
                self.full_content_cache.clear()
                # Do NOT pre-cache everything; only load what's on the current page.
                self.reset_search_state()
                self.filter_and_paginate_items()
        
        self.content_stack.set_visible_child_name("content")
        return GLib.SOURCE_REMOVE

    def add_keyboard_shortcuts(self):
        win_key_controller = Gtk.EventControllerKey()
        win_key_controller.connect("key-pressed", self.on_win_key_pressed)
        self.add_controller(win_key_controller)
        list_key_controller = Gtk.EventControllerKey()
        list_key_controller.connect("key-pressed", self.on_list_key_pressed)
        self.listbox.add_controller(list_key_controller)

    def on_win_key_pressed(self, controller, keyval, keycode, state):
        if self.search_entry.has_focus(): return False
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up) and self.prev_button.get_sensitive():
            self.on_prev_page_clicked(None)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down) and self.next_button.get_sensitive():
            self.on_next_page_clicked(None)
            return True
        elif keyval == Gdk.KEY_F5:
            self.load_history()
            return True
        return False

    def on_list_key_pressed(self, controller, keyval, keycode, state):
        selected_row = self.listbox.get_selected_row()
        if not selected_row: return False
        
        if keyval == Gdk.KEY_Return:
            selected_row.on_copy_clicked(None)
            return True
        if keyval == Gdk.KEY_Delete:
            selected_row.on_delete_clicked(None)
            return True
        return False
        
    def on_search_changed_debounced(self, entry):
        if self.search_timeout_id > 0: 
            GLib.source_remove(self.search_timeout_id)
        self.search_timeout_id = GLib.timeout_add(300, self.on_search_or_filter_changed)

    def get_full_content_for_item(self, item_text):
        """Get full content for an item, using cache for performance."""
        if item_text in self.full_content_cache:
            return self.full_content_cache[item_text]
        content = get_full_clipboard_content(item_text)
        self.full_content_cache[item_text] = content
        return content

    # ---------- Incremental search helpers (page-at-a-time) ----------

    def reset_search_state(self):
        self._cancel_search_scan()
        self.search_state = None

    def _cancel_search_scan(self):
        if self.search_state and self.search_state.get('scan_source_id'):
            GLib.source_remove(self.search_state['scan_source_id'])
            self.search_state['scan_source_id'] = 0

    def item_matches_search_quick(self, item_text, term_lower):
        """Quick check without decoding: only uses preview text or 'Image' placeholder."""
        if is_image_item(item_text):
            return 'image'.startswith(term_lower) or (term_lower in 'image')
        preview = preview_text_of(item_text)
        return term_lower in preview.lower()

    def item_matches_search_full(self, item_text, term_lower):
        """Decode and check, only for text items that failed quick check."""
        if is_image_item(item_text):
            return False
        full = self.get_full_content_for_item(item_text) or ""
        return term_lower in full.lower()

    def start_incremental_search_until(self, target_count):
        """Incrementally scan items until we have target_count results or reach end."""
        self._cancel_search_scan()
        if not self.search_state:
            return

        def step():
            state = self.search_state
            type_filtered = state['type_filtered']
            term_lower = state['term'].lower()

            # Process a small chunk per idle to keep UI responsive
            budget = 24
            while budget > 0 and state['scan_index'] < len(type_filtered) and len(state['results']) < target_count:
                item = type_filtered[state['scan_index']]
                state['scan_index'] += 1

                if self.item_matches_search_quick(item, term_lower):
                    state['results'].append(item)
                else:
                    # Only decode if needed, and only for text
                    if not is_image_item(item) and self.item_matches_search_full(item, term_lower):
                        state['results'].append(item)

                budget -= 1

            if len(state['results']) >= target_count or state['scan_index'] >= len(type_filtered):
                # Done with this page's quota or exhausted the list
                state['fully_scanned'] = state['scan_index'] >= len(type_filtered)
                state['scan_source_id'] = 0
                self.render_current_page()
                return GLib.SOURCE_REMOVE

            # Keep scanning on next idle
            return GLib.SOURCE_CONTINUE

        self.search_state['scan_source_id'] = GLib.idle_add(step)

    # ---------- End incremental search helpers ----------

    def on_filter_toggled(self, button, mode):
        if button.get_active():
            self.current_filter_mode = mode
            self.on_search_or_filter_changed()

    def on_search_or_filter_changed(self, *args):
        self.current_page = 0
        self.reset_search_state()
        self.filter_and_paginate_items()
        return GLib.SOURCE_REMOVE

    def filter_and_paginate_items(self):
        # Filter by type without loading contents
        is_text = lambda item: not is_image_item(item)
        is_img = lambda item: is_image_item(item)

        if self.current_filter_mode == "text":
            type_filtered = [item for item in self.all_items if is_text(item)]
        elif self.current_filter_mode == "image":
            type_filtered = [item for item in self.all_items if is_img(item)]
        else:
            type_filtered = self.all_items

        search_text = self.search_entry.get_text().strip()

        self.cleanup_visible_rows()

        # Clear current list rows
        child = self.listbox.get_first_child()
        while child:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()

        if not search_text:
            # No search: just show the current page slice; do not decode anything.
            total_items = len(type_filtered)
            if total_items == 0:
                if self.current_filter_mode != "all":
                    self.show_placeholder("No items match your filter.", "edit-find-symbolic")
                else:
                    self.show_placeholder("Clipboard history is empty.", "edit-paste-symbolic")
                self.total_pages = 0
                self.update_page_controls_nonsearch(0)
                return

            self.total_pages = math.ceil(total_items / self.items_per_page)
            self.current_page = max(0, min(self.current_page, self.total_pages - 1))
            start_index = self.current_page * self.items_per_page
            items_for_page = type_filtered[start_index : start_index + self.items_per_page]

            self.visible_rows = []
            for item_text in items_for_page:
                row = ClipboardRow(item_text, self, None)
                self.listbox.append(row)
                self.visible_rows.append(row)
            
            self.update_page_controls_nonsearch(total_items)
            return

        # Search mode: incremental, one page at a time.
        if not self.search_state or self.search_state.get('term') != search_text or self.search_state.get('type_filtered') is not type_filtered:
            self.search_state = {
                'term': search_text,
                'type_filtered': type_filtered,
                'results': [],
                'scan_index': 0,
                'fully_scanned': False,
                'scan_source_id': 0,
            }

        # Ensure we have enough results to render this page
        target_count = (self.current_page + 1) * self.items_per_page

        # Show a lightweight "searching" placeholder while we scan for this page
        self.show_placeholder("Searching…", "edit-find-symbolic")
        self.update_page_controls_search()
        self.start_incremental_search_until(target_count)

    def render_current_page(self):
        """Render rows for the current page using current search state."""
        if not self.search_state:
            return

        self.cleanup_visible_rows()

        # Clear current list rows
        child = self.listbox.get_first_child()
        while child:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()

        results = self.search_state['results']
        fully_scanned = self.search_state['fully_scanned']

        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page

        if len(results) == 0 and fully_scanned:
            self.show_placeholder("No items match your search.", "edit-find-symbolic")
            self.update_page_controls_search()
            return

        # If we don't yet have enough results to fill this page and we can still scan, keep waiting.
        if len(results) <= start_index and not fully_scanned:
            # Keep placeholder; controls already updated
            return

        slice_items = results[start_index:end_index]

        self.visible_rows = []
        for item_text in slice_items:
            row = ClipboardRow(item_text, self, self.search_state['term'])
            self.listbox.append(row)
            self.visible_rows.append(row)

        self.update_page_controls_search()

    def show_placeholder(self, text, icon_name):
        child = self.listbox.get_first_child()
        while child:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()
        placeholder_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                 margin_top=40, margin_bottom=40, vexpand=True, hexpand=True,
                                 halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        label = Gtk.Label(label=text, css_classes=["dim-label"], justify=Gtk.Justification.CENTER)
        placeholder_box.append(icon)
        placeholder_box.append(label)
        placeholder_row = Gtk.ListBoxRow(selectable=False, activatable=False)
        placeholder_row.set_child(placeholder_box)
        self.listbox.append(placeholder_row)

    def on_prev_page_clicked(self, button):
        if self.current_page > 0:
            self.current_page -= 1
            # In search mode, we already have cached results for previous pages.
            self.filter_and_paginate_items()

    def on_next_page_clicked(self, button):
        # In search mode, next availability depends on whether we have more results or can scan more.
        self.current_page += 1
        self.filter_and_paginate_items()

    def update_page_controls_nonsearch(self, total_items):
        filter_text = {"all": "items", "text": "text items", "image": "images"}[self.current_filter_mode]
        self.stats_label.set_text(f"{total_items} {filter_text}")
        
        has_pagination = total_items > 0 and self.total_pages > 1
        if has_pagination:
            self.page_info_label.set_text(f"Page {self.current_page + 1} of {self.total_pages}")
        else:
            self.page_info_label.set_text("")
        
        self.prev_button.set_sensitive(self.current_page > 0)
        self.next_button.set_sensitive(self.current_page < self.total_pages - 1)
        self.prev_button.set_visible(has_pagination)
        self.next_button.set_visible(has_pagination)

    def update_page_controls_search(self):
        """Controls for search mode where total count is unknown until fully scanned."""
        if not self.search_state:
            self.stats_label.set_text("")
            self.page_info_label.set_text("")
            self.prev_button.set_sensitive(False)
            self.next_button.set_sensitive(False)
            self.prev_button.set_visible(False)
            self.next_button.set_visible(False)
            return

        results = self.search_state['results']
        fully_scanned = self.search_state['fully_scanned']

        # Show results so far; add '+' if not fully scanned
        suffix = "" if fully_scanned else "+"
        self.stats_label.set_text(f"Search results: {len(results)}{suffix}")
        self.page_info_label.set_text(f"Page {self.current_page + 1}")

        # Prev enabled if not on first page
        can_prev = self.current_page > 0

        # Next enabled if we already have more results than the end of this page OR we can still scan further
        page_end = (self.current_page + 1) * self.items_per_page
        can_next = (len(results) > page_end) or (not fully_scanned)

        # Show controls when search is active
        self.prev_button.set_visible(True)
        self.next_button.set_visible(True)
        self.prev_button.set_sensitive(can_prev)
        self.next_button.set_sensitive(can_next)

    def on_clear_clicked(self, button):
        dialog = Adw.MessageDialog.new(self.get_root(), "Clear Clipboard History?",
                                       "This will permanently delete all items.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear All")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self.on_clear_dialog_response)
        dialog.present()

    def on_clear_dialog_response(self, dialog, response):
        if response == "clear":
            try:
                subprocess.run(['cliphist', 'wipe'], check=True)
                self.full_content_cache.clear()
                self.load_history(is_initial_load=True) # Reload with spinner
                self.show_toast("Clipboard history cleared.")
            except Exception as e:
                print(f"Error wiping history: {e}")
                self.show_toast("Error: Failed to clear history.")
        dialog.close()
        
    def show_toast(self, text):
        if self.toast_overlay:
            self.toast_overlay.add_toast(Adw.Toast.new(text))
