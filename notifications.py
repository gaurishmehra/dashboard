import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gio, Gdk
import json
import os
from datetime import datetime, timezone
import warnings
import subprocess

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Represents a single, interactive row in the notification list.
# This class is responsible for displaying the notification's content,
# handling its visual state (like expanded or collapsed), and loading its icon.
class NotificationRow(Gtk.ListBoxRow):
    # Initializes the notification row with its data and sets up its basic properties.
    def __init__(self, notification):
        super().__init__()
        self.notification = notification
        self.expanded = False

        self.set_activatable(True)
        self.add_css_class("notification-row")

        self.create_ui()

    # Constructs all the visual elements (widgets) that make up the notification row.
    # This includes the icon, text labels, and the expandable body section.
    def create_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                             margin_top=12, margin_bottom=12, margin_start=16, margin_end=16)

        self.avatar = Adw.Avatar(size=48, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.load_icon()

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                              hexpand=True,
                              valign=Gtk.Align.CENTER)

        app_name_label = Gtk.Label(label=self.notification.get('app_name', 'System'),
                                   halign=Gtk.Align.START, xalign=0, css_classes=["app-name"])

        summary_label = Gtk.Label(label=self.notification.get('summary', 'No summary'),
                                  halign=Gtk.Align.START, xalign=0, ellipsize=Pango.EllipsizeMode.END,
                                  max_width_chars=50, css_classes=["summary-label"])

        content_box.append(app_name_label)
        content_box.append(summary_label)

        time_label = Gtk.Label(label=self.format_timestamp(),
                               valign=Gtk.Align.CENTER,
                               margin_end=6,
                               css_classes=["time-label"])

        self.expand_icon = Gtk.Image(icon_name="pan-end-symbolic", css_classes=["expand-icon"], valign=Gtk.Align.CENTER)

        header_box.append(self.avatar)
        header_box.append(content_box)
        header_box.append(time_label)

        body_text = self.notification.get('body', '').strip()
        if body_text:
            header_box.append(self.expand_icon)

        main_box.append(header_box)

        if body_text:
            self.body_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                              transition_duration=250, reveal_child=False)

            body_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                     margin_start=76, margin_end=16, margin_bottom=16)

            body_label = Gtk.Label(label=body_text, halign=Gtk.Align.START, xalign=0,
                                   wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                   css_classes=["body-label"])

            if len(body_text.splitlines()) > 6 or len(body_text) > 400:
                scrolled_body = Gtk.ScrolledWindow(css_classes=["notification-body-scroll"])
                scrolled_body.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                scrolled_body.set_max_content_height(150)
                scrolled_body.set_child(body_label)
                body_container.append(scrolled_body)
            else:
                body_container.append(body_label)

            self.body_revealer.set_child(body_container)
            main_box.append(self.body_revealer)
        else:
            self.body_revealer = None

        self.set_child(main_box)

    # Loads the notification's icon. It first tries to load an image from the provided
    # path and falls back to displaying the first letter of the app's name if it fails.
    def load_icon(self):
        icon_path = self.notification.get('icon', '')
        app_name = self.notification.get('app_name', 'System')

        if icon_path and os.path.exists(icon_path):
            try:
                texture = Gdk.Texture.new_from_filename(icon_path)
                self.avatar.set_custom_image(texture)
                return
            except GLib.Error as e:
                print(f"GDK texture error for '{icon_path}': {e}, falling back.")

        self.avatar.set_text(app_name[0].upper() if app_name else "S")

    # Formats the notification timestamp into a human-readable, relative string like
    # "now", "5m ago", "14:30", "yesterday", or "Jan 15".
    def format_timestamp(self):
        ts_str = self.notification.get('timestamp', '')
        if not ts_str: return "just now"

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

    # Toggles the visibility of the notification's body content, animating
    # the expansion and collapse.
    def toggle_expanded(self):
        if not self.body_revealer:
            return

        self.expanded = not self.expanded
        self.body_revealer.set_reveal_child(self.expanded)

        if self.expanded:
            self.expand_icon.set_from_icon_name("pan-up-symbolic")
            self.add_css_class("expanded")
        else:
            self.expand_icon.set_from_icon_name("pan-end-symbolic")
            self.remove_css_class("expanded")

    # Determines if the notification's content matches a given search text.
    # This is used for filtering the notification list.
    def matches_search(self, search_text):
        if not search_text:
            return True

        search_lower = search_text.lower()
        content = (
            self.notification.get('app_name', '') + ' ' +
            self.notification.get('summary', '') + ' ' +
            self.notification.get('body', '')
        ).lower()

        return search_lower in content

# The main container widget for the entire notifications panel.
# It manages loading notifications from a file, displaying them in a list,
# and provides controls for searching and clearing the history.
class NotificationsWidget(Gtk.Box):
    # Sets up the initial state of the widget, including the path to the
    # notifications data file.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.notifications_file = os.path.expanduser("~/.local/share/dunst/notifications.json")
        self.all_notifications = []
        self.notification_rows = []

        self.file_monitor = None
        self.last_mtime = 0

        self.is_active = False

        self.create_ui()

    # Starts the widget's operations, like loading data for the first time
    # and beginning to monitor the data file for changes.
    def activate(self):
        if self.is_active: return
        self.is_active = True
        print("NotificationsWidget Activated")
        self.reload_notifications()
        self.setup_file_monitor()

    # Stops the widget's background activities, such as the file monitor,
    # to conserve resources when it is not visible.
    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        print("NotificationsWidget Deactivated")
        if self.file_monitor:
            self.file_monitor.cancel()
            self.file_monitor = None

    # Builds the user interface for the notifications panel, including the
    # header, search bar, clear button, and the scrollable list.
    def create_ui(self):
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                             margin_top=20, margin_bottom=16, margin_start=20, margin_end=20)

        header_box.append(Gtk.Label(label="Notifications", halign=Gtk.Align.START, css_classes=["title-large"]))

        self.search_entry = Gtk.SearchEntry(placeholder_text="Search...", hexpand=True)
        self.search_entry.connect("search-changed", self.on_search_changed)
        header_box.append(self.search_entry)

        clear_button = Gtk.Button(icon_name="edit-clear-all-symbolic", tooltip_text="Clear History", css_classes=["circular"])
        clear_button.connect("clicked", self.on_clear_clicked)
        header_box.append(clear_button)

        scrolled_area = Gtk.ScrolledWindow(vexpand=True, css_classes=["invisible-scroll"])
        scrolled_area.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE,
                                   css_classes=["notifications-list"],
                                   margin_start=16, margin_end=16, margin_bottom=16)
        self.listbox.connect("row-activated", lambda lb, row: row.toggle_expanded())

        scrolled_area.set_child(self.listbox)

        self.append(header_box)
        self.append(scrolled_area)

    # Sets up a monitor that watches the notifications JSON file for changes,
    # triggering an automatic reload when the file is modified.
    def setup_file_monitor(self):
        if self.file_monitor: return
        try:
            notif_dir = os.path.dirname(self.notifications_file)
            if not os.path.exists(notif_dir):
                os.makedirs(notif_dir, exist_ok=True)
            if not os.path.exists(self.notifications_file):
                with open(self.notifications_file, 'w') as f: json.dump([], f)

            file = Gio.File.new_for_path(self.notifications_file)
            self.file_monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, None)
            self.file_monitor.connect("changed", lambda *args: GLib.timeout_add(250, self.reload_notifications))
            print("File monitor started for notifications.")
        except Exception as e:
            print(f"Failed to set up file monitor: {e}")

    # Reads the notification data from the JSON file, sorts them by date,
    # and updates the listbox with the new content.
    def reload_notifications(self):
        if not self.is_active: return GLib.SOURCE_REMOVE

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
            self.notification_rows = [NotificationRow(n) for n in self.all_notifications]
            self.filter_notifications()

        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading notifications file: {e}")
            self.all_notifications = []
            self.notification_rows = []
            self.filter_notifications()

        return GLib.SOURCE_REMOVE

    # Callback function that is triggered when the text in the search entry changes.
    def on_search_changed(self, search_entry):
        self.filter_notifications()

    # Clears and repopulates the listbox based on the current search text,
    # showing only the notifications that match the query.
    def filter_notifications(self):
        search_text = self.search_entry.get_text().strip()

        for child in list(self.listbox):
             self.listbox.remove(child)

        if not self.notification_rows:
            self.show_placeholder("No notifications yet.")
            return

        filtered_count = 0
        for row in self.notification_rows:
            if row.matches_search(search_text):
                self.listbox.append(row)
                filtered_count += 1

        if filtered_count == 0:
            self.show_placeholder(f"No results for '{search_text}'")

    # Displays a placeholder message in the list area, used when there are
    # no notifications or no search results to display.
    def show_placeholder(self, text):
        placeholder = Gtk.Label(label=text, css_classes=["dim-label"],
                                margin_top=50, margin_bottom=50)
        self.listbox.append(placeholder)

    # Handles the click event for the 'Clear History' button, deleting the
    # contents of the notifications file and any cached images.
    def on_clear_clicked(self, button):
        try:
            with open(self.notifications_file, 'w') as f:
                json.dump([], f)

            images_dir = os.path.expanduser("~/.local/share/dunst/images")
            if os.path.exists(images_dir):
                subprocess.run(['rm', '-rf', f'{images_dir}/*'], shell=True, check=False)

            self.search_entry.set_text("")
            print("Notification history cleared.")

        except Exception as e:
            print(f"Error clearing notifications: {e}")