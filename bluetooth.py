import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango
import subprocess
import json
import re
import threading
import queue
import warnings
import os

warnings.filterwarnings("ignore")

# This class represents a single row for a Bluetooth device in the UI.
# It displays the device's icon, name, status, and a button to connect or disconnect.
class BluetoothDeviceWidget(Gtk.Box):
    # Sets up the widget with the device's info and connection status.
    def __init__(self, device_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.device_info = device_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()

    # Builds the visual elements of the device row.
    def create_ui(self):
        self.add_css_class("info-tile")
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        icon_name = self.get_device_icon()
        device_icon = Gtk.Image()
        device_icon.set_from_icon_name(icon_name)
        device_icon.set_pixel_size(32)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        name_label = Gtk.Label(label=self.device_info.get('name', 'Unknown Device'))
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(25)

        status_text = "Connected" if self.is_connected else "Available"
        battery_level = self.device_info.get('battery', None)

        if self.is_connected and battery_level is not None:
            status_text = f"Connected • {battery_level}% battery"

        self.status_label = Gtk.Label(label=status_text)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("device-status")

        info_box.append(name_label)
        info_box.append(self.status_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(16, 16)
        self.spinner.set_visible(False)

        self.connect_button = Gtk.Button()
        self.connect_button.set_size_request(80, 36)
        self.connect_button.add_css_class("action-button")

        if self.is_connected:
            self.connect_button.set_label("Disconnect")
            self.connect_button.add_css_class("destructive-action")
        else:
            self.connect_button.set_label("Connect")
            self.connect_button.add_css_class("suggested-action")

        button_box.append(self.spinner)
        button_box.append(self.connect_button)

        self.append(device_icon)
        self.append(info_box)
        self.append(button_box)

    # Shows or hides the loading spinner while a connection is in progress.
    def set_loading(self, loading):
        self.is_loading = loading
        if loading:
            self.spinner.set_visible(True)
            self.spinner.start()
            self.connect_button.set_sensitive(False)
            self.connect_button.set_label("...")
            self.status_label.set_text("Connecting..." if not self.is_connected else "Disconnecting...")
        else:
            self.spinner.set_visible(False)
            self.spinner.stop()
            self.connect_button.set_sensitive(True)

            if self.is_connected:
                self.connect_button.set_label("Disconnect")
                battery_level = self.device_info.get('battery', None)
                if battery_level is not None:
                    self.status_label.set_text(f"Connected • {battery_level}% battery")
                else:
                    self.status_label.set_text("Connected")
            else:
                self.connect_button.set_label("Connect")
                self.status_label.set_text("Available")

    # Updates the widget's appearance based on its new connection state.
    def update_connection_state(self, connected):
        self.is_connected = connected

        self.connect_button.remove_css_class("destructive-action")
        self.connect_button.remove_css_class("suggested-action")

        if connected:
            self.connect_button.set_label("Disconnect")
            self.connect_button.add_css_class("destructive-action")
            battery_level = self.device_info.get('battery', None)
            if battery_level is not None:
                self.status_label.set_text(f"Connected • {battery_level}% battery")
            else:
                self.status_label.set_text("Connected")
        else:
            self.connect_button.set_label("Connect")
            self.connect_button.add_css_class("suggested-action")
            self.status_label.set_text("Available")

    # Chooses a suitable icon based on the device's type or name.
    def get_device_icon(self):
        device_type = self.device_info.get('type', '').lower()
        name = self.device_info.get('name', '').lower()

        if 'headphone' in device_type or 'audio' in device_type or 'headset' in name or 'buds' in name or 'earphone' in name:
            return "audio-headphones-symbolic"
        elif 'mouse' in device_type or 'mouse' in name:
            return "input-mouse-symbolic"
        elif 'keyboard' in device_type or 'keyboard' in name:
            return "input-keyboard-symbolic"
        elif 'phone' in device_type or 'phone' in name:
            return "phone-symbolic"
        elif 'computer' in device_type or 'laptop' in name or 'pc' in name:
            return "computer-symbolic"
        elif 'speaker' in name or 'soundbar' in name:
            return "audio-speakers-symbolic"
        else:
            return "bluetooth-symbolic"

# This is the main widget for the Bluetooth panel. It manages the global
# Bluetooth state, discovers devices, and displays them in lists.
class BluetoothWidget(Gtk.Box):
    # Initializes the main widget, sets up device lists, and starts a
    # background thread to handle Bluetooth commands without freezing the UI.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.connected_devices = []
        self.available_devices = []
        self.bluetooth_enabled = False
        self.device_widgets = {}

        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()

        self.is_active = False
        self.update_timer_id = None
        self.scan_timer_id = None

        self.create_ui()

    # This is called when the widget becomes visible. It starts the
    # periodic checks for Bluetooth status and device scanning.
    def activate(self):
        if self.is_active:
            return
        self.is_active = True
        print("BluetoothWidget Activated")
        self.update_bluetooth_status()
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(3, self.update_bluetooth_status)
            self.scan_timer_id = GLib.timeout_add_seconds(10, self.scan_devices)

    # This is called when the widget is hidden. It stops the periodic
    # checks and scanning to save system resources.
    def deactivate(self):
        if not self.is_active:
            return
        self.is_active = False
        print("BluetoothWidget Deactivated")
        if self.update_timer_id:
            GLib.source_remove(self.update_timer_id)
            self.update_timer_id = None
        if self.scan_timer_id:
            GLib.source_remove(self.scan_timer_id)
            self.scan_timer_id = None

    # This is the worker that runs in a separate thread. It picks up
    # commands from a queue and executes them safely in the background.
    def command_worker(self):
        while True:
            try:
                command = self.command_queue.get(timeout=1)
                if command:
                    subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Bluetooth command error: {e}")

    # Constructs the main layout of the widget, including the header
    # with the title, scan button, and on/off switch.
    def create_ui(self):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_box.set_margin_bottom(16)

        title_label = Gtk.Label(label="Bluetooth")
        title_label.add_css_class("title-large")
        title_label.set_hexpand(True)
        title_label.set_halign(Gtk.Align.START)

        self.bluetooth_switch = Gtk.Switch()
        self.bluetooth_switch.set_valign(Gtk.Align.CENTER)
        self.bluetooth_switch.connect("notify::active", self.on_bluetooth_toggled)

        scan_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Scan for devices")
        scan_button.add_css_class("circular")
        scan_button.connect("clicked", lambda b: self.scan_devices())

        header_box.append(title_label)
        header_box.append(scan_button)
        header_box.append(self.bluetooth_switch)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        scrolled_window.add_css_class("invisible-scroll")

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        scrolled_window.set_child(self.content_box)

        self.append(header_box)
        self.append(scrolled_window)

    # A utility function to execute a shell command and return its output.
    def run_bluetooth_command(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"Bluetooth command error: {e}")
            return ""

    # Checks if Bluetooth is currently powered on and updates the device list accordingly.
    def update_bluetooth_status(self):
        if not self.is_active:
            return False

        status_output = self.run_bluetooth_command("bluetoothctl show")
        self.bluetooth_enabled = "Powered: yes" in status_output

        self.bluetooth_switch.handler_block_by_func(self.on_bluetooth_toggled)
        self.bluetooth_switch.set_active(self.bluetooth_enabled)
        self.bluetooth_switch.handler_unblock_by_func(self.on_bluetooth_toggled)

        if self.bluetooth_enabled:
            self.update_devices()
        else:
            self.show_bluetooth_disabled()

        return True

    # Fetches the latest lists of connected and available (paired) devices.
    def update_devices(self):
        connected_output = self.run_bluetooth_command("bluetoothctl devices Connected")
        self.connected_devices = self.parse_device_list(connected_output, connected=True)

        paired_output = self.run_bluetooth_command("bluetoothctl devices Paired")
        paired_devices = self.parse_device_list(paired_output, connected=False)

        connected_macs = {d['mac'] for d in self.connected_devices}
        self.available_devices = [d for d in paired_devices if d['mac'] not in connected_macs]

        self.update_ui()

    # Processes the raw text output from bluetoothctl into a clean list of devices.
    def parse_device_list(self, output, connected=False):
        devices = []
        if not output:
            return devices

        for line in output.split('\n'):
            if line.startswith('Device '):
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]

                    device_info = {
                        'mac': mac,
                        'name': name,
                        'type': self.get_device_type(mac, name),
                        'battery': self.get_battery_level(mac, name) if connected else None
                    }
                    devices.append(device_info)

        return devices

    # Tries to determine what kind of device it is (e.g., audio, input)
    # by looking at its name and other technical details.
    def get_device_type(self, mac, name):
        info_output = self.run_bluetooth_command(f"bluetoothctl info {mac}")

        name_lower = name.lower()
        if any(word in name_lower for word in ['headphone', 'headset', 'buds', 'earphone', 'airpods']):
            return "audio"
        elif any(word in name_lower for word in ['mouse']):
            return "input"
        elif any(word in name_lower for word in ['keyboard']):
            return "input"
        elif any(word in name_lower for word in ['phone']):
            return "phone"
        elif any(word in name_lower for word in ['speaker', 'soundbar']):
            return "audio"

        if "Class:" in info_output:
            class_match = re.search(r'Class: 0x(\w+)', info_output)
            if class_match:
                device_class = class_match.group(1)
                try:
                    major_class = (int(device_class, 16) >> 8) & 0x1F
                    if major_class == 4:
                        return "audio"
                    elif major_class == 5:
                        return "input"
                    elif major_class == 2:
                        return "phone"
                except ValueError:
                    pass

        if "Audio Sink" in info_output or "A2DP" in info_output:
            return "audio"
        elif "Human Interface Device" in info_output or "HID" in info_output:
            return "input"

        return "unknown"

    # This function attempts to find the battery level of a device, correctly parsing
    # both decimal and hexadecimal values from the system.
    def get_battery_level(self, mac, name):
        print(f"Getting battery level for {name} ({mac})")
        mac_formatted = mac.replace(':', '_')

        # Method 1: Try D-Bus directly using gdbus (most reliable)
        try:
            cmd = (
                f"gdbus call --system --dest org.bluez "
                f"--object-path /org/bluez/hci0/dev_{mac_formatted} "
                f"--method org.freedesktop.DBus.Properties.Get "
                f"org.bluez.Battery1 Percentage"
            )
            dbus_output = self.run_bluetooth_command(f"{cmd} 2>/dev/null")

            if dbus_output:
                print(f"D-Bus output for {name}: {dbus_output}")
                # Updated regex to capture hex (0x..) or decimal (\d+) values
                match = re.search(r'(?:byte|uint8)\s+(0x[0-9a-fA-F]+|\d+)', dbus_output)
                if match:
                    value_str = match.group(1)
                    # int(value, 0) automatically handles '0x' prefixes for hex
                    battery_level = int(value_str, 0)
                    if 0 <= battery_level <= 100:
                        print(f"Battery found via D-Bus: {battery_level}% for {name} (parsed from '{value_str}')")
                        return battery_level
        except Exception as e:
            print(f"Error querying D-Bus for battery: {e}")

        # Method 2: Try bluetoothctl info (good fallback, also handles hex/dec)
        try:
            info_output = self.run_bluetooth_command(f"bluetoothctl info {mac}")
            if info_output:
                # First, try to find the simple decimal value in parentheses, e.g. (74)
                match = re.search(r'Battery Percentage:.*?\((d+)\)', info_output)
                if match:
                    battery_level = int(match.group(1))
                    if 0 <= battery_level <= 100:
                        print(f"Battery found via bluetoothctl (decimal): {battery_level}% for {name}")
                        return battery_level

                # If not found, try to parse the main value which could be hex or dec
                match = re.search(r'Battery Percentage:\s+(0x[0-9a-fA-F]+|\d+)', info_output)
                if match:
                    value_str = match.group(1)
                    battery_level = int(value_str, 0)
                    if 0 <= battery_level <= 100:
                        print(f"Battery found via bluetoothctl (hex/dec): {battery_level}% for {name} (parsed from '{value_str}')")
                        return battery_level
        except Exception as e:
            print(f"Error querying bluetoothctl for battery: {e}")

        # Method 3: Check /sys/class/power_supply (less common but worth trying)
        try:
            for dir_name in os.listdir('/sys/class/power_supply/'):
                dir_path = f'/sys/class/power_supply/{dir_name}'
                if any(s in dir_name.lower() for s in [mac.replace(':', ''), name.lower().replace(' ', '_')]):
                    capacity_path = os.path.join(dir_path, 'capacity')
                    if os.path.exists(capacity_path):
                        with open(capacity_path, 'r') as f:
                            capacity = f.read().strip()
                            if capacity.isdigit():
                                battery_level = int(capacity)
                                if 0 <= battery_level <= 100:
                                    print(f"Battery found via /sys: {battery_level}% for {name}")
                                    return battery_level
        except (OSError, IOError) as e:
            print(f"Could not read /sys/class/power_supply: {e}")

        print(f"No reliable battery information found for {name} ({mac})")
        return None

    # Starts a scan for nearby Bluetooth devices for a few seconds.
    def scan_devices(self):
        if not self.bluetooth_enabled:
            return False

        self.command_queue.put("bluetoothctl scan on")
        GLib.timeout_add_seconds(5, lambda: self.command_queue.put("bluetoothctl scan off"))

        return True

    # This function is called when the user clicks the main on/off switch.
    def on_bluetooth_toggled(self, switch, *args):
        if switch.get_active():
            self.command_queue.put("bluetoothctl power on")
        else:
            self.command_queue.put("bluetoothctl power off")

    # Handles clicks on the "Connect" or "Disconnect" button for a specific device.
    def on_device_connect(self, device_info, connect=True):
        mac = device_info['mac']

        widget = self.device_widgets.get(mac)
        if widget:
            widget.set_loading(True)

        if connect:
            self.command_queue.put(f"bluetoothctl connect {mac}")
        else:
            self.command_queue.put(f"bluetoothctl disconnect {mac}")

        def update_and_hide_loading():
            self.update_devices()
            if widget:
                widget.set_loading(False)
            return False

        GLib.timeout_add_seconds(3, update_and_hide_loading)

    # Clears and rebuilds the entire list of devices in the UI.
    def update_ui(self):
        child = self.content_box.get_first_child()
        while child:
            self.content_box.remove(child)
            child = self.content_box.get_first_child()

        self.device_widgets.clear()

        if self.connected_devices:
            connected_label = Gtk.Label(label="Connected Devices")
            connected_label.add_css_class("section-title")
            connected_label.set_halign(Gtk.Align.START)
            connected_label.set_margin_start(8)
            connected_label.set_margin_bottom(8)
            self.content_box.append(connected_label)

            for device in self.connected_devices:
                device_widget = BluetoothDeviceWidget(device, is_connected=True)
                device_widget.connect_button.connect("clicked",
                    lambda b, d=device: self.on_device_connect(d, connect=False))
                self.device_widgets[device['mac']] = device_widget
                self.content_box.append(device_widget)

        if self.available_devices:
            if self.connected_devices:
                spacer = Gtk.Box()
                spacer.set_size_request(-1, 16)
                self.content_box.append(spacer)

            available_label = Gtk.Label(label="Available Devices")
            available_label.add_css_class("section-title")
            available_label.set_halign(Gtk.Align.START)
            available_label.set_margin_start(8)
            available_label.set_margin_bottom(8)
            self.content_box.append(available_label)

            for device in self.available_devices:
                device_widget = BluetoothDeviceWidget(device, is_connected=False)
                device_widget.connect_button.connect("clicked",
                    lambda b, d=device: self.on_device_connect(d, connect=True))
                self.device_widgets[device['mac']] = device_widget
                self.content_box.append(device_widget)

        if not self.connected_devices and not self.available_devices:
            self.show_no_devices()

    # Displays a message indicating that no devices were found.
    def show_no_devices(self):
        no_devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        no_devices_box.set_valign(Gtk.Align.CENTER)
        no_devices_box.set_vexpand(True)

        icon = Gtk.Image.new_from_icon_name("bluetooth-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")

        message_label = Gtk.Label(label="No Bluetooth Devices Found")
        message_label.add_css_class("title-large")
        message_label.add_css_class("dim-label")

        hint_label = Gtk.Label(label="Make sure devices are in pairing mode and click scan")
        hint_label.add_css_class("dim-label")

        no_devices_box.append(icon)
        no_devices_box.append(message_label)
        no_devices_box.append(hint_label)

        self.content_box.append(no_devices_box)

    # Displays a message informing the user that Bluetooth is turned off.
    def show_bluetooth_disabled(self):
        child = self.content_box.get_first_child()
        while child:
            self.content_box.remove(child)
            child = self.content_box.get_first_child()

        disabled_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        disabled_box.set_valign(Gtk.Align.CENTER)
        disabled_box.set_vexpand(True)

        icon = Gtk.Image.new_from_icon_name("bluetooth-disabled-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")

        message_label = Gtk.Label(label="Bluetooth is Disabled")
        message_label.add_css_class("title-large")
        message_label.add_css_class("dim-label")

        hint_label = Gtk.Label(label="Enable bluetooth to see your devices")
        hint_label.add_css_class("dim-label")

        disabled_box.append(icon)
        disabled_box.append(message_label)
        disabled_box.append(hint_label)

        self.content_box.append(disabled_box)