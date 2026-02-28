import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

# Note: System tray indicator (AppIndicator3) uses GTK3 which conflicts with GTK4.
# We'll use a subprocess-based approach for the tray icon instead.
_HAS_INDICATOR = False

# Performance tuning based on GPU type:
# - NVIDIA: Use GL renderer (hardware accelerated, fast on discrete GPU)
# - Intel/AMD iGPU: Use Cairo renderer (avoids GPU driver overhead)
import os
import subprocess

# Cache file for GPU renderer detection (avoids 100-200ms glxinfo call on every start)
_GPU_CACHE_FILE = os.path.join(
    os.path.expanduser("~"), ".cache", "dashboard_gpu_renderer"
)


def _detect_gpu_renderer():
    """Detect active GPU and return optimal GSK renderer. Uses cache for speed."""
    if "GSK_RENDERER" in os.environ:
        return os.environ["GSK_RENDERER"]  # User override

    # Check cache first (instant)
    try:
        if os.path.exists(_GPU_CACHE_FILE):
            with open(_GPU_CACHE_FILE, "r") as f:
                cached = f.read().strip()
                if cached in ("gl", "cairo", "vulkan", "ngl"):
                    return cached
    except Exception:
        pass

    renderer = "cairo"  # Default for Intel/AMD iGPU
    try:
        # Check the active GPU renderer
        result = subprocess.run(["glxinfo"], capture_output=True, text=True, timeout=2)
        output = result.stdout.upper()
        for line in output.split("\n"):
            if "OPENGL RENDERER" in line or "RENDERER STRING" in line:
                if "NVIDIA" in line:
                    renderer = "gl"
                break
        # Cache the result for next time
        os.makedirs(os.path.dirname(_GPU_CACHE_FILE), exist_ok=True)
        with open(_GPU_CACHE_FILE, "w") as f:
            f.write(renderer)
    except Exception:
        pass

    return renderer


os.environ["GSK_RENDERER"] = _detect_gpu_renderer()
# Reduce texture atlas size to prevent VRAM pressure on iGPU
if "GSK_GPU_SKIP_MIPMAPS" not in os.environ:
    os.environ["GSK_GPU_SKIP_MIPMAPS"] = "1"

from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import warnings
import sys
import threading
import concurrent.futures
import subprocess
import signal
from app_logging import module_print
from ui_helpers import STACK_TRANSITION_MS

print = module_print(__name__)

# Only suppress specific known-benign warnings, not everything
warnings.filterwarnings("ignore", category=DeprecationWarning, module="gi")

# Module-level ThreadPoolExecutor - reused across all async operations
# This avoids the overhead of creating/destroying threads repeatedly
_shared_executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)

# Lazy imports - modules are loaded on-demand in background threads
_widget_classes = {}
_import_lock = threading.Lock()


def _import_widget_class(name):
    """Import a widget class lazily and cache it."""
    with _import_lock:
        if name in _widget_classes:
            return _widget_classes[name]

        if name == "media":
            from media_player import MediaPlayerWidget

            _widget_classes[name] = MediaPlayerWidget
        elif name == "notifications":
            from notifications import NotificationsWidget

            _widget_classes[name] = NotificationsWidget
        elif name == "clipboard":
            from clipboard import ClipboardWidget

            _widget_classes[name] = ClipboardWidget
        elif name == "bluetooth":
            from bluetooth import BluetoothWidget

            _widget_classes[name] = BluetoothWidget
        elif name == "wifi":
            from wifi import WiFiWidget

            _widget_classes[name] = WiFiWidget
        elif name == "weather":
            from weather import WeatherWidget

            _widget_classes[name] = WeatherWidget

        return _widget_classes.get(name)


# This class defines the main window for the application. It holds the overall
# structure, including the sidebar and the content area, and manages switching
# between the different widget views.
class Dashboard(Adw.ApplicationWindow):
    # This is the constructor for the window. It sets up initial properties
    # like the title and size, connects the escape key for closing the window,
    # and calls the method to build the user interface.
    def __init__(self, initial_view="media", hide_on_close=True, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Media Controller")
        self.set_default_size(800, 600)
        self.set_size_request(800, 600)
        self.hide_on_close = hide_on_close

        self.initial_view = initial_view
        self.current_view_name = initial_view
        self.current_widget = None
        self.widgets = {}
        self._pending_widget_loads = set()

        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)

        # Connect close-request to hide instead of destroy
        self.connect("close-request", self.on_close_request)

        self.create_ui()

    def on_close_request(self, window):
        """Hide the window instead of destroying it (for system tray mode)."""
        if self.hide_on_close:
            self.set_visible(False)
            # Deactivate current widget to save resources while hidden
            if self.current_widget and hasattr(self.current_widget, "deactivate"):
                self.current_widget.deactivate()
            return True  # Prevent default close behavior
        return False  # Allow normal close

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

        self.notifications_button = Gtk.Button(
            icon_name="preferences-system-notifications-symbolic"
        )
        self.notifications_button.set_size_request(60, 60)
        self.notifications_button.add_css_class("circular")
        self.notifications_button.add_css_class("sidebar-button")
        self.notifications_button.set_tooltip_text("Notifications")
        self.notifications_button.connect(
            "clicked", lambda b: self.switch_view("notifications")
        )

        self.clipboard_button = Gtk.Button(icon_name="edit-paste-symbolic")
        self.clipboard_button.set_size_request(60, 60)
        self.clipboard_button.add_css_class("circular")
        self.clipboard_button.add_css_class("sidebar-button")
        self.clipboard_button.set_tooltip_text("Clipboard History")
        self.clipboard_button.connect(
            "clicked", lambda b: self.switch_view("clipboard")
        )

        self.bluetooth_button = Gtk.Button(icon_name="bluetooth-symbolic")
        self.bluetooth_button.set_size_request(60, 60)
        self.bluetooth_button.add_css_class("circular")
        self.bluetooth_button.add_css_class("sidebar-button")
        self.bluetooth_button.set_tooltip_text("Bluetooth")
        self.bluetooth_button.connect(
            "clicked", lambda b: self.switch_view("bluetooth")
        )

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
        sidebar.append(self.clipboard_button)
        sidebar.append(self.bluetooth_button)
        sidebar.append(self.wifi_button)
        sidebar.append(self.weather_button)

        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_transition_duration(STACK_TRANSITION_MS)

        # Shared loading view for lazy-loaded tabs.
        self._view_loading_name = "_view_loading"
        self._view_loading_label = Gtk.Label(
            label="Loading...", css_classes=["dim-label"], halign=Gtk.Align.CENTER
        )
        view_loading_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        view_loading_spinner = Gtk.Spinner(spinning=True, width_request=28, height_request=28)
        view_loading_box.append(view_loading_spinner)
        view_loading_box.append(self._view_loading_label)
        self.content_stack.add_named(view_loading_box, self._view_loading_name)

        leaflet.append(sidebar)
        leaflet.append(self.content_stack)

        # Load CSS first so the window appears styled immediately
        self.load_css()

        # Use idle_add instead of timeout for faster widget creation
        GLib.idle_add(self.create_and_activate_initial_widgets)

    # This function is called after a short delay to avoid blocking the UI thread on startup.
    # It creates the initial view widget immediately and loads others in parallel background threads.
    def create_and_activate_initial_widgets(self):
        try:
            # Show a minimal loading indicator immediately (so UI appears instantly)
            loading_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=12,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
            )
            spinner = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
            loading_box.append(spinner)
            self.content_stack.add_named(loading_box, "_loading")
            self.content_stack.set_visible_child_name("_loading")

            # Start importing all widget classes in parallel (this is the slow part)
            widget_names = [
                "media",
                "notifications",
                "clipboard",
                "bluetooth",
                "wifi",
                "weather",
            ]
            import_futures = {
                name: _shared_executor.submit(_import_widget_class, name)
                for name in widget_names
            }

            # Store for later use
            self._import_futures = import_futures
            self._loading_box = loading_box
            self._widget_names = widget_names

            # Use a done callback instead of tight polling to avoid extra wakeups.
            initial_future = self._import_futures.get(self.initial_view)
            if initial_future:
                initial_future.add_done_callback(
                    lambda _future: GLib.idle_add(self._finish_initial_widget_load)
                )

        except Exception as e:
            print(f"Error creating widgets: {e}")
            import traceback

            traceback.print_exc()

        return GLib.SOURCE_REMOVE

    def _finish_initial_widget_load(self):
        """Called when initial widget import is complete."""
        try:
            initial_class = self._import_futures[self.initial_view].result()

            # Create the initial widget on main thread (GTK requirement)
            if self.initial_view == "clipboard":
                self.widgets[self.initial_view] = initial_class(
                    toast_overlay=self.toast_overlay
                )
            else:
                self.widgets[self.initial_view] = initial_class()

            if self.initial_view == "media":
                media_container = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL,
                    valign=Gtk.Align.CENTER,
                    vexpand=True,
                )
                media_container.append(self.widgets[self.initial_view])
                self.content_stack.add_named(media_container, self.initial_view)
            else:
                self.content_stack.add_named(
                    self.widgets[self.initial_view], self.initial_view
                )
            self.content_stack.set_visible_child_name(self.initial_view)
            self.current_widget = self.widgets[self.initial_view]

            # Remove loading placeholder
            self.content_stack.remove(self._loading_box)

            if hasattr(self.current_widget, "activate"):
                self.current_widget.activate()

            self.update_sidebar_buttons()

            # Warm remaining imports in background only. Widgets are created lazily
            # when the user actually opens that view.
            remaining_names = [n for n in self._widget_names if n != self.initial_view]
            if remaining_names:
                threading.Thread(
                    target=self._warm_imports, args=(remaining_names,), daemon=True
                ).start()

        except Exception as e:
            print(f"Error finishing widget load: {e}")

    def _warm_imports(self, widget_names):
        """Warm module imports in background without constructing GTK widgets."""
        for name in widget_names:
            try:
                future = self._import_futures.get(name)
                if future:
                    future.result()
            except Exception as e:
                print(f"Error importing widget '{name}': {e}")

    def _create_widget_instance(self, view_name, widget_class):
        """Create and add a widget to the stack on-demand."""
        if view_name in self.widgets:
            return self.widgets[view_name]

        if view_name == "clipboard":
            widget = widget_class(toast_overlay=self.toast_overlay)
        else:
            widget = widget_class()

        self.widgets[view_name] = widget
        if view_name == "media":
            widget.set_halign(Gtk.Align.CENTER)
            widget.set_valign(Gtk.Align.CENTER)
            media_container = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                halign=Gtk.Align.FILL,
                valign=Gtk.Align.FILL,
                hexpand=True,
                vexpand=True,
            )
            media_container.append(widget)
            self.content_stack.add_named(media_container, view_name)
        else:
            self.content_stack.add_named(widget, view_name)
        return widget

    def _on_view_import_ready(self, view_name):
        """Finish creating a lazily-loaded widget after import completes."""
        try:
            future = getattr(self, "_import_futures", {}).get(view_name)
            widget_class = future.result() if future else _import_widget_class(view_name)
            if not widget_class:
                return GLib.SOURCE_REMOVE

            self._create_widget_instance(view_name, widget_class)
            self._pending_widget_loads.discard(view_name)

            # Only switch/activate if user still wants this view.
            if self.current_view_name == view_name:
                self.content_stack.set_visible_child_name(view_name)
                self.current_widget = self.widgets.get(view_name)
                if self.current_widget and hasattr(self.current_widget, "activate"):
                    self.current_widget.activate()
        except Exception as e:
            self._pending_widget_loads.discard(view_name)
            print(f"Error finishing lazy view load '{view_name}': {e}")
        return GLib.SOURCE_REMOVE

    # This is the core logic for changing views. It deactivates the background tasks
    # of the old widget, switches the visible page in the Gtk.Stack, and then activates
    # the background tasks for the new widget. This ensures only one widget is active
    # at a time, preventing lag and unnecessary resource usage.
    def switch_view(self, view_name):
        if view_name == self.current_view_name:
            return

        try:
            if self.current_widget and hasattr(self.current_widget, "deactivate"):
                self.current_widget.deactivate()

            self.current_view_name = view_name
            self.update_sidebar_buttons()

            # Check if widget exists yet (might still be loading/importing)
            if view_name not in self.widgets:
                widget_class = _widget_classes.get(view_name)
                if widget_class:
                    self._create_widget_instance(view_name, widget_class)
                else:
                    future = getattr(self, "_import_futures", {}).get(view_name)
                    if future and not future.done():
                        self._view_loading_label.set_text(
                            f"Loading {view_name.title()}..."
                        )
                        self.content_stack.set_visible_child_name(self._view_loading_name)
                        self.current_widget = None
                        if view_name not in self._pending_widget_loads:
                            self._pending_widget_loads.add(view_name)
                            future.add_done_callback(
                                lambda _f, name=view_name: GLib.idle_add(
                                    self._on_view_import_ready, name
                                )
                            )
                        return
                    if future:
                        widget_class = future.result()
                    else:
                        widget_class = _import_widget_class(view_name)
                    if widget_class:
                        self._create_widget_instance(view_name, widget_class)

            self.content_stack.set_visible_child_name(view_name)
            self.current_widget = self.widgets.get(view_name)
            if self.current_widget and hasattr(self.current_widget, "activate"):
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
            "clipboard": self.clipboard_button,
            "bluetooth": self.bluetooth_button,
            "wifi": self.wifi_button,
            "weather": self.weather_button,
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
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
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
        super().__init__(
            application_id="one.gaurish.Dashboard",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            **kwargs,
        )
        self.initial_view = initial_view
        self.win = None
        self.start_hidden = False  # For --load flag
        self.connect("activate", self.on_activate)
        self.connect("command-line", self.on_command_line)
        self.add_main_option(
            "view", ord("v"), 0, GLib.OptionArg.STRING, "Open specific view", "VIEW"
        )
        self.add_main_option(
            "quit",
            ord("q"),
            0,
            GLib.OptionArg.NONE,
            "Quit the application completely",
            None,
        )
        self.add_main_option(
            "load",
            ord("l"),
            0,
            GLib.OptionArg.NONE,
            "Load app in background without showing UI",
            None,
        )
        self.add_main_option(
            "toggle",
            ord("t"),
            0,
            GLib.OptionArg.NONE,
            "Toggle window visibility (show/hide)",
            None,
        )

    def on_command_line(self, app, command_line):
        """Handle command line - allows re-opening from second instance."""
        options = command_line.get_options_dict()

        # Handle --quit flag
        if options.contains("quit"):
            if self.win:
                self.win.hide_on_close = False
                self.win.close()
            self.quit()
            return 0

        # Handle --toggle flag
        if options.contains("toggle"):
            if self.win:
                if self.win.get_visible():
                    # Window visible -> hide it
                    self.win.set_visible(False)
                    if self.win.current_widget and hasattr(
                        self.win.current_widget, "deactivate"
                    ):
                        self.win.current_widget.deactivate()
                else:
                    # Window hidden -> show it
                    self.show_window()
            return 0

        # Handle --load flag (start in background)
        if options.contains("load"):
            self.start_hidden = True
            self.activate()  # Create window but don't show
            return 0

        # Handle --view flag
        if options.contains("view"):
            view = options.lookup_value("view").get_string()
            valid_views = [
                "media",
                "notifications",
                "clipboard",
                "bluetooth",
                "wifi",
                "weather",
            ]
            if view in valid_views:
                self.initial_view = view
                if self.win:
                    self.win.switch_view(view)

        self.activate()
        return 0

    # Handle command line options (for primary instance)
    def do_handle_local_options(self, options):
        # Return -1 to let the application continue (command-line handler will process)
        return -1

    def show_window(self):
        """Show the main window and activate current widget."""
        if self.win:
            self.win.set_visible(True)
            self.win.present()
            # Reactivate current widget
            if self.win.current_widget and hasattr(self.win.current_widget, "activate"):
                self.win.current_widget.activate()

    def show_view(self, view_name):
        """Show window with specific view."""
        if self.win:
            self.win.switch_view(view_name)
        self.show_window()

    def quit_app(self):
        """Properly quit the application."""
        # Clean up shared executor
        _shared_executor.shutdown(wait=False)
        if self.win:
            self.win.hide_on_close = False
            self.win.close()
        self.quit()

    # This method is automatically called by Gtk when the application is launched.
    # Its main job is to create an instance of our main Dashboard window and show it
    # to the user.
    def on_activate(self, app):
        try:
            if not self.win:
                # First activation - create window
                # hide_on_close=True keeps app running in background when window is closed
                self.win = Dashboard(
                    application=app, initial_view=self.initial_view, hide_on_close=True
                )

            # Show the window unless started with --load
            if self.start_hidden:
                self.start_hidden = False  # Reset for future activations
            else:
                self.show_window()
        except Exception as e:
            print(f"Error creating dashboard: {e}")


# This is the main entry point function for the script. It creates an
# instance of our DashboardApp and tells it to run, starting the Gtk event loop.
def main():
    try:
        app = DashboardApp()
        return app.run(sys.argv)
    except Exception as e:
        print(f"Error starting app: {e}")
        return 1


if __name__ == "__main__":
    main()
