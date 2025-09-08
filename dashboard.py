import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import warnings
import os
import argparse
import sys

warnings.filterwarnings("ignore")

from media_player import MediaPlayerWidget
from notifications import NotificationsWidget
# --- Import the new widget ---
from clipboard import ClipboardWidget
# ---
from bluetooth import BluetoothWidget
from wifi import WiFiWidget
from weather import WeatherWidget

# This class defines the main window for the application. It holds the overall
# structure, including the sidebar and the content area, and manages switching
# between the different widget views.
class Dashboard(Adw.ApplicationWindow):
    # This is the constructor for the window. It sets up initial properties
    # like the title and size, connects the escape key for closing the window,
    # and calls the method to build the user interface.
    def __init__(self, initial_view="media", **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Media Controller")
        self.set_default_size(800, 600)
        self.set_size_request(800, 600) 
        
        self.initial_view = initial_view
        self.current_view_name = initial_view
        self.current_widget = None
        self.widgets = {}
        
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        self.create_ui()
    
    # This function handles key press events for the main window. It specifically
    # checks if the Escape key was pressed and closes the application if it was.
    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
    
    # This method builds the entire user interface, including the modern layout
    # with a sidebar and a content area (Gtk.Stack). It creates the navigation
    # buttons and defers the creation of the actual content widgets to improve
    # the application's startup time.
    def create_ui(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)
        
        leaflet = Adw.Leaflet()
        leaflet.set_can_navigate_back(True)
        self.toast_overlay.set_child(leaflet)
        
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar.set_size_request(90, -1)
        sidebar.add_css_class("sidebar")
        
        sidebar.set_margin_top(20)
        sidebar.set_margin_bottom(20)
        sidebar.set_margin_start(10)
        sidebar.set_margin_end(10)
        sidebar.set_valign(Gtk.Align.CENTER)

        self.media_button = Gtk.Button(icon_name="audio-headphones-symbolic")
        self.media_button.set_size_request(60, 60)
        self.media_button.add_css_class("circular")
        self.media_button.add_css_class("sidebar-button")
        self.media_button.set_tooltip_text("Media Player")
        self.media_button.connect("clicked", lambda b: self.switch_view("media"))
        
        self.notifications_button = Gtk.Button(icon_name="preferences-system-notifications-symbolic")
        self.notifications_button.set_size_request(60, 60)
        self.notifications_button.add_css_class("circular")
        self.notifications_button.add_css_class("sidebar-button")
        self.notifications_button.set_tooltip_text("Notifications")
        self.notifications_button.connect("clicked", lambda b: self.switch_view("notifications"))

        # --- Create the clipboard button ---
        self.clipboard_button = Gtk.Button(icon_name="edit-paste-symbolic")
        self.clipboard_button.set_size_request(60, 60)
        self.clipboard_button.add_css_class("circular")
        self.clipboard_button.add_css_class("sidebar-button")
        self.clipboard_button.set_tooltip_text("Clipboard History")
        self.clipboard_button.connect("clicked", lambda b: self.switch_view("clipboard"))
        # ---

        self.bluetooth_button = Gtk.Button(icon_name="bluetooth-symbolic")
        self.bluetooth_button.set_size_request(60, 60)
        self.bluetooth_button.add_css_class("circular")
        self.bluetooth_button.add_css_class("sidebar-button")
        self.bluetooth_button.set_tooltip_text("Bluetooth")
        self.bluetooth_button.connect("clicked", lambda b: self.switch_view("bluetooth"))

        self.wifi_button = Gtk.Button(icon_name="network-wireless-symbolic")
        self.wifi_button.set_size_request(60, 60)
        self.wifi_button.add_css_class("circular")
        self.wifi_button.add_css_class("sidebar-button")
        self.wifi_button.set_tooltip_text("WiFi")
        self.wifi_button.connect("clicked", lambda b: self.switch_view("wifi"))
        
        self.weather_button = Gtk.Button(icon_name="weather-clear-symbolic")
        self.weather_button.set_size_request(60, 60)
        self.weather_button.add_css_class("circular")
        self.weather_button.add_css_class("sidebar-button")
        self.weather_button.set_tooltip_text("Weather")
        self.weather_button.connect("clicked", lambda b: self.switch_view("weather"))
        
        # --- Add buttons to sidebar in the correct order ---
        sidebar.append(self.media_button)
        sidebar.append(self.notifications_button)
        sidebar.append(self.clipboard_button) # Added here
        sidebar.append(self.bluetooth_button)
        sidebar.append(self.wifi_button)
        sidebar.append(self.weather_button)
        # ---
        
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(300)
        
        leaflet.append(sidebar)
        leaflet.append(self.content_stack)
        
        GLib.timeout_add(50, self.create_and_activate_initial_widgets)
        
        self.load_css()

    # This function is called after a short delay to avoid blocking the UI thread on startup.
    # It creates instances of all the different view widgets, adds them to the content stack,
    # and then activates the initial, default view.
    def create_and_activate_initial_widgets(self):
        try:
            self.widgets["media"] = MediaPlayerWidget()
            self.widgets["notifications"] = NotificationsWidget()
            # --- Instantiate the new widget, passing the toast overlay ---
            self.widgets["clipboard"] = ClipboardWidget(toast_overlay=self.toast_overlay)
            # ---
            self.widgets["bluetooth"] = BluetoothWidget()
            self.widgets["wifi"] = WiFiWidget()
            self.widgets["weather"] = WeatherWidget()
    
            self.content_stack.add_named(self.widgets["media"], "media")
            self.content_stack.add_named(self.widgets["notifications"], "notifications")
            # --- Add the new widget to the stack ---
            self.content_stack.add_named(self.widgets["clipboard"], "clipboard")
            # ---
            self.content_stack.add_named(self.widgets["bluetooth"], "bluetooth")
            self.content_stack.add_named(self.widgets["wifi"], "wifi")
            self.content_stack.add_named(self.widgets["weather"], "weather")

            # Use the initial view instead of hardcoded "media"
            self.content_stack.set_visible_child_name(self.initial_view)
            self.current_widget = self.widgets[self.initial_view]

            if hasattr(self.current_widget, 'activate'):
                self.current_widget.activate() 
            
            self.update_sidebar_buttons()
            
        except Exception as e:
            print(f"Error creating widgets: {e}")
        
        return GLib.SOURCE_REMOVE
    
    # This is the core logic for changing views. It deactivates the background tasks
    # of the old widget, switches the visible page in the Gtk.Stack, and then activates
    # the background tasks for the new widget. This ensures only one widget is active
    # at a time, preventing lag and unnecessary resource usage.
    def switch_view(self, view_name):
        if view_name == self.current_view_name:
            return

        try:
            if self.current_widget and hasattr(self.current_widget, 'deactivate'):
                self.current_widget.deactivate()

            self.current_view_name = view_name
            self.content_stack.set_visible_child_name(view_name)
            self.update_sidebar_buttons()

            self.current_widget = self.widgets.get(view_name)
            if self.current_widget and hasattr(self.current_widget, 'activate'):
                self.current_widget.activate()

        except Exception as e:
            print(f"Error switching view: {e}")
    
    # This is a helper function that visually updates the sidebar buttons.
    # It adds a special 'active' CSS class to the button corresponding to the
    # currently displayed view, making it easy for the user to see where they are.
    def update_sidebar_buttons(self):
        buttons = {
            "media": self.media_button,
            "notifications": self.notifications_button,
            # --- Add the new button to the map ---
            "clipboard": self.clipboard_button,
            # ---
            "bluetooth": self.bluetooth_button,
            "wifi": self.wifi_button,
            "weather": self.weather_button
        }
        for name, button in buttons.items():
            if name == self.current_view_name:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    # This method loads the CSS from an external file for better organization
    def load_css(self):
        css_provider = Gtk.CssProvider()
        css_file_path = os.path.join(os.path.dirname(__file__), "style.css")
        
        try:
            css_provider.load_from_path(css_file_path)
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Error loading CSS file: {e}")

# This is the main application class that Gtk uses to manage the app's lifecycle.
# It ensures the application has a unique ID and connects the 'activate' signal,
# which is the primary starting point for the app.
class DashboardApp(Adw.Application):
    # The constructor for the application class. It sets the unique application ID
    # required by Gtk and connects the 'activate' signal to the on_activate method.
    def __init__(self, initial_view="media", **kwargs):
        super().__init__(application_id="one.gaurish.Dashboard", **kwargs)
        self.initial_view = initial_view
        self.connect('activate', self.on_activate)
        
        # Add command line option handling
        self.add_main_option("view", ord("v"), 0,
                            GLib.OptionArg.STRING, "Open specific view", "VIEW")
    
    # Handle command line options
    def do_handle_local_options(self, options):
        if options.contains("view"):
            view = options.lookup_value("view").get_string()
            valid_views = ["media", "notifications", "clipboard", "bluetooth", "wifi", "weather"]
            
            if view in valid_views:
                self.initial_view = view
            else:
                print(f"Invalid view '{view}'. Valid options: {', '.join(valid_views)}")
                return 1
        
        return -1  # Continue processing
    
    # This method is automatically called by Gtk when the application is launched.
    # Its main job is to create an instance of our main Dashboard window and show it
    # to the user.
    def on_activate(self, app):
        try:
            self.win = Dashboard(application=app, initial_view=self.initial_view)
            self.win.present()
        except Exception as e:
            print(f"Error creating dashboard: {e}")

# Parse command line arguments and validate view option
def parse_args():
    parser = argparse.ArgumentParser(description='Media Controller Dashboard')
    parser.add_argument('--view', '-v', 
                       choices=['media', 'notifications', 'clipboard', 'bluetooth', 'wifi', 'weather'],
                       default='media',
                       help='Open specific view on startup (default: media)')
    
    return parser.parse_args()

# This is the main entry point function for the script. It creates an
# instance of our DashboardApp and tells it to run, starting the Gtk event loop.
def main():
    try:
        args = parse_args()
        app = DashboardApp(initial_view=args.view)
        return app.run(sys.argv)
    except Exception as e:
        print(f"Error starting app: {e}")
        return 1

if __name__ == '__main__':
    main()