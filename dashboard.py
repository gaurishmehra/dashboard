import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib
import warnings

warnings.filterwarnings("ignore")

from media_player import MediaPlayerWidget
from notifications import NotificationsWidget
from adb import ADBWidget
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Media Controller")
        self.set_default_size(800, 600)
        self.set_size_request(800, 600) 
        
        self.current_view_name = "media"
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
        toast_overlay = Adw.ToastOverlay()
        self.set_content(toast_overlay)
        
        leaflet = Adw.Leaflet()
        leaflet.set_can_navigate_back(True)
        toast_overlay.set_child(leaflet)
        
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
        
        self.adb_button = Gtk.Button(icon_name="phone-symbolic")
        self.adb_button.set_size_request(60, 60)
        self.adb_button.add_css_class("circular")
        self.adb_button.add_css_class("sidebar-button")
        self.adb_button.set_tooltip_text("ADB Controller")
        self.adb_button.connect("clicked", lambda b: self.switch_view("adb"))

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
        
        sidebar.append(self.media_button)
        sidebar.append(self.notifications_button)
        sidebar.append(self.adb_button)
        sidebar.append(self.bluetooth_button)
        sidebar.append(self.wifi_button)
        sidebar.append(self.weather_button)
        
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(300)
        
        leaflet.append(sidebar)
        leaflet.append(self.content_stack)
        
        GLib.timeout_add(50, self.create_and_activate_initial_widgets)
        
        self.apply_enhanced_css()

    # This function is called after a short delay to avoid blocking the UI thread on startup.
    # It creates instances of all the different view widgets, adds them to the content stack,
    # and then activates the initial, default view.
    def create_and_activate_initial_widgets(self):
        try:
            self.widgets["media"] = MediaPlayerWidget()
            self.widgets["notifications"] = NotificationsWidget()
            self.widgets["adb"] = ADBWidget()
            self.widgets["bluetooth"] = BluetoothWidget()
            self.widgets["wifi"] = WiFiWidget()
            self.widgets["weather"] = WeatherWidget()
    
            self.content_stack.add_named(self.widgets["media"], "media")
            self.content_stack.add_named(self.widgets["notifications"], "notifications")
            self.content_stack.add_named(self.widgets["adb"], "adb")
            self.content_stack.add_named(self.widgets["bluetooth"], "bluetooth")
            self.content_stack.add_named(self.widgets["wifi"], "wifi")
            self.content_stack.add_named(self.widgets["weather"], "weather")

            self.content_stack.set_visible_child_name("media")
            self.current_widget = self.widgets["media"]

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
            "adb": self.adb_button,
            "bluetooth": self.bluetooth_button,
            "wifi": self.wifi_button,
            "weather": self.weather_button
        }
        for name, button in buttons.items():
            if name == self.current_view_name:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    # This method loads and applies all the custom CSS styling for the application.
    # It defines the look and feel of the window, sidebar, buttons, and all other
    # components to create a polished and consistent user experience.
    def apply_enhanced_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        window {
            background: rgba(30, 30, 35, 0.7);
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sidebar {
            background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
            border-radius: 12px;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sidebar-button {
            background: transparent;
            border: 1px solid transparent;
            color: rgba(255, 255, 255, 0.6);
            transition: all 250ms ease-in-out;
            border-radius: 30px;
        }

        .sidebar-button:hover {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.9);
        }
        
        .sidebar-button.active {
            background: rgba(80, 160, 255, 0.25);
            color: white;
            border: 1px solid rgba(80, 160, 255, 0.5);
            box-shadow: 0 0 12px rgba(80, 160, 255, 0.5);
        }
        
        searchbar, entry {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            color: white;
            padding: 8px 12px;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.2);
        }
        
        searchbar:focus, entry:focus {
            border-color: rgba(80, 160, 255, 0.6);
            box-shadow: 0 0 0 3px rgba(80, 160, 255, 0.2);
        }
        
        .notification-body-scroll { background: transparent; }
        
        .notification-body-scroll scrollbar {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
            min-width: 8px;
            opacity: 1;
        }

        .notification-body-scroll scrollbar slider {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            min-width: 8px;
            min-height: 20px;
        }

        .location-label {
            font-size: 13px;
            color: rgba(255, 255, 255, 0.7);
            font-weight: 500;
        }

        .temperature-label {
            font-size: 48px;
            font-weight: bold;
            color: white;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
        }

        .weather-desc {
            font-size: 16px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
        }

        .weather-detail-label {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
            font-weight: 500;
        }

        .weather-detail-value {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.95);
            font-weight: bold;
        }

        .hourly-scroll {
            background: transparent;
        }

        .hourly-scroll scrollbar {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
            min-height: 8px;
        }

        .hourly-scroll scrollbar slider {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            min-height: 8px;
        }

        .hourly-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px 8px;
            transition: all 200ms ease;
        }

        .hourly-card:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: scale(0.95);
        }

        .hourly-time {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.7);
            font-weight: 500;
        }

        .hourly-temp {
            font-size: 13px;
            color: white;
            font-weight: bold;
        }

        .hourly-precip {
            font-size: 9px;
            color: rgba(100, 150, 255, 0.9);
            font-weight: 500;
        }

        .daily-row {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 12px 16px;
            transition: all 200ms ease;
        }

        .daily-row:hover {
            background: rgba(255, 255, 255, 0.06);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .daily-day {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
        }

        .daily-temp-max {
            font-size: 14px;
            color: white;
            font-weight: bold;
        }

        .daily-temp-min {
            font-size: 13px;
            color: rgba(255, 255, 255, 0.7);
        }

        .daily-precip {
            font-size: 11px;
            color: rgba(100, 150, 255, 0.9);
            font-weight: 500;
        }
        
        .invisible-scroll { background: transparent; }
        .invisible-scroll scrollbar { min-width: 0px; opacity: 0; }
        .invisible-scroll scrollbar slider { min-width: 0px; opacity: 0; }
        .notification-icon-bg { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 24px; }
        .notifications-list { background: transparent; }
        .notification-row { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; margin: 4px 0px; transition: all 150ms ease; }
        .notification-row:hover { background: rgba(255, 255, 255, 0.07); border-color: rgba(255, 255, 255, 0.15); }
        .notification-row.expanded { background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.2); }
        .app-name { font-size: 11px; font-weight: bold; color: rgba(255, 255, 255, 0.9); text-transform: uppercase; letter-spacing: 0.5px; }
        .time-label { font-size: 10px; color: rgba(255, 255, 255, 0.6); }
        .summary-label { font-size: 13px; font-weight: 500; color: rgba(255, 255, 255, 0.95); }
        .body-label { font-size: 12px; color: rgba(255, 255, 255, 0.8); line-height: 1.4; }
        .expand-icon { color: rgba(255, 255, 255, 0.6); transition: transform 150ms ease; }
        .title-large { font-size: 20px; font-weight: bold; color: white; }
        .dim-label { color: rgba(255, 255, 255, 0.6); }
        .title-label { font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.95); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .artist-label { font-size: 13px; color: rgba(255, 255, 255, 0.8); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .control-button { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transition: all 100ms ease; }
        .control-button:hover { background: rgba(255, 255, 255, 0.2); transform: scale(1.05); }
        .play-button { background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.4); color: rgba(255, 255, 255, 0.95); transition: all 100ms ease; }
        .play-button:hover { background: rgba(255, 255, 255, 0.3); transform: scale(1.05); }
        .player-icon { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.7); transition: all 100ms ease; }
        .player-icon:hover { background: rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transform: scale(1.05); }
        .player-icon.suggested-action { background: rgba(80, 160, 255, 0.2); color: white; border: 1px solid rgba(80, 160, 255, 0.4); }
        .volume-scale trough { background: rgba(0, 0, 0, 0.3); border-radius: 10px; }
        .volume-scale highlight { background: rgba(255, 255, 255, 0.6); border-radius: 10px; }
        .device-header { background: rgba(255, 255, 255, 0.05); border-radius: 16px; transition: all 150ms ease; padding: 12px 16px; }
        .info-tile { background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05)); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 12px; padding: 12px; transition: all 200ms ease; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
        .info-tile:hover { transform: scale(0.95); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2); }
        .section-title { font-size: 14px; font-weight: bold; color: rgba(255, 255, 255, 0.9); text-transform: uppercase; letter-spacing: 0.5px; }
        .action-button { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 12px; color: rgba(255, 255, 255, 0.9); transition: all 150ms ease; }
        .action-button:hover { background: rgba(255, 255, 255, 0.15); border-color: rgba(255, 255, 255, 0.3); transform: scale(0.95); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }

        """)
        
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

# This is the main application class that Gtk uses to manage the app's lifecycle.
# It ensures the application has a unique ID and connects the 'activate' signal,
# which is the primary starting point for the app.
class DashboardApp(Adw.Application):
    # The constructor for the application class. It sets the unique application ID
    # required by Gtk and connects the 'activate' signal to the on_activate method.
    def __init__(self, **kwargs):
        super().__init__(application_id="com.gaurish.Dashboard", **kwargs)
        self.connect('activate', self.on_activate)
    
    # This method is automatically called by Gtk when the application is launched.
    # Its main job is to create an instance of our main Dashboard window and show it
    # to the user.
    def on_activate(self, app):
        try:
            self.win = Dashboard(application=app)
            self.win.present()
        except Exception as e:
            print(f"Error creating dashboard: {e}")

# This is the main entry point function for the script. It creates an
# instance of our DashboardApp and tells it to run, starting the Gtk event loop.
def main():
    try:
        app = DashboardApp()
        return app.run()
    except Exception as e:
        print(f"Error starting app: {e}")
        return 1

if __name__ == '__main__':
    main()