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

warnings.filterwarnings("ignore")

class BluetoothDeviceWidget(Gtk.Box):
    def __init__(self, device_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.device_info = device_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()
    
    def create_ui(self):
        self.add_css_class("info-tile")
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        
        # Device icon based on type
        icon_name = self.get_device_icon()
        device_icon = Gtk.Image()
        device_icon.set_from_icon_name(icon_name)
        device_icon.set_pixel_size(32)
        
        # Device info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        name_label = Gtk.Label(label=self.device_info.get('name', 'Unknown Device'))
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(25)
        
        # Status and battery info
        status_text = "Connected" if self.is_connected else "Available"
        battery_level = self.device_info.get('battery', None)
        
        if self.is_connected and battery_level is not None:
            status_text = f"Connected • {battery_level}% battery"
        
        self.status_label = Gtk.Label(label=status_text)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("device-status")
        
        info_box.append(name_label)
        info_box.append(self.status_label)
        
        # Connection button with loading capability
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Loading spinner (initially hidden)
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
    
    def set_loading(self, loading):
        """Show/hide loading spinner and update button state"""
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
            
            # Reset button and status
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
    
    def update_connection_state(self, connected):
        """Update the widget's connection state"""
        self.is_connected = connected
        
        # Remove old CSS classes
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
    
    def get_device_icon(self):
        """Get appropriate icon based on device type"""
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

class BluetoothWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.connected_devices = []
        self.available_devices = []
        self.bluetooth_enabled = False
        self.device_widgets = {}  # Track widgets by MAC address
        
        # Command queue for async execution
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        
        # **LAG FIX: Properties to manage activation state**
        self.is_active = False
        self.update_timer_id = None
        self.scan_timer_id = None
        
        self.create_ui()
    
    def activate(self):
        """Called when the widget becomes visible."""
        if self.is_active:
            return
        self.is_active = True
        print("BluetoothWidget Activated")
        self.update_bluetooth_status()
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(3, self.update_bluetooth_status)
            # Start device scanning every 10 seconds
            self.scan_timer_id = GLib.timeout_add_seconds(10, self.scan_devices)

    def deactivate(self):
        """Called when the widget is hidden."""
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

    def command_worker(self):
        """Worker thread for executing bluetooth commands"""
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
    
    def create_ui(self):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        
        # Header with bluetooth toggle
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
        
        # Scrollable content
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        scrolled_window.add_css_class("invisible-scroll")
        
        # Content container
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        scrolled_window.set_child(self.content_box)
        
        self.append(header_box)
        self.append(scrolled_window)
    
    def run_bluetooth_command(self, command):
        """Run bluetooth command and return output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"Bluetooth command error: {e}")
            return ""
    
    def update_bluetooth_status(self):
        """Update bluetooth status and devices"""
        if not self.is_active:
            return False
        
        # Check if bluetooth is enabled
        status_output = self.run_bluetooth_command("bluetoothctl show")
        self.bluetooth_enabled = "Powered: yes" in status_output
        
        # Update switch without triggering callback
        self.bluetooth_switch.handler_block_by_func(self.on_bluetooth_toggled)
        self.bluetooth_switch.set_active(self.bluetooth_enabled)
        self.bluetooth_switch.handler_unblock_by_func(self.on_bluetooth_toggled)
        
        if self.bluetooth_enabled:
            self.update_devices()
        else:
            self.show_bluetooth_disabled()
        
        return True
    
    def update_devices(self):
        """Update connected and available devices"""
        # Get connected devices
        connected_output = self.run_bluetooth_command("bluetoothctl devices Connected")
        self.connected_devices = self.parse_device_list(connected_output, connected=True)
        
        # Get paired devices
        paired_output = self.run_bluetooth_command("bluetoothctl devices Paired")
        paired_devices = self.parse_device_list(paired_output, connected=False)
        
        # Filter out connected devices from paired list
        connected_macs = {d['mac'] for d in self.connected_devices}
        self.available_devices = [d for d in paired_devices if d['mac'] not in connected_macs]
        
        self.update_ui()
    
    def parse_device_list(self, output, connected=False):
        """Parse bluetoothctl device list output"""
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
    
    def get_device_type(self, mac, name):
        """Get device type from bluetoothctl info and device name"""
        info_output = self.run_bluetooth_command(f"bluetoothctl info {mac}")
        
        # First check the name for obvious indicators
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
        
        # Look for device class or appearance in bluetoothctl info
        if "Class:" in info_output:
            class_match = re.search(r'Class: 0x(\w+)', info_output)
            if class_match:
                device_class = class_match.group(1)
                try:
                    # Parse major device class
                    major_class = (int(device_class, 16) >> 8) & 0x1F
                    if major_class == 4:  # Audio/Video
                        return "audio"
                    elif major_class == 5:  # Peripheral
                        return "input"
                    elif major_class == 2:  # Phone
                        return "phone"
                except ValueError:
                    pass
        
        # Check for UUID services
        if "Audio Sink" in info_output or "A2DP" in info_output:
            return "audio"
        elif "Human Interface Device" in info_output or "HID" in info_output:
            return "input"
        
        return "unknown"
    
    def get_battery_level(self, mac, name):
        """Get battery level for connected device using multiple methods"""
        battery_level = None
        
        try:
            # Method 1: Try bluetoothctl info (most direct)
            info_output = self.run_bluetooth_command(f"bluetoothctl info {mac}")
            battery_match = re.search(r'Battery Percentage: \(0x\w+\) (\d+)', info_output)
            if battery_match:
                battery_level = int(battery_match.group(1))
                print(f"Battery via bluetoothctl info: {battery_level}% for {name}")
                return battery_level
            
            # Method 2: Try UPower for known device paths
            upower_output = self.run_bluetooth_command("upower -i $(upower -e | grep -i BAT)")
            if upower_output:
                # Look for bluetooth devices in UPower
                percentage_match = re.search(r'percentage:\s+(\d+)%', upower_output)
                if percentage_match:
                    battery_level = int(percentage_match.group(1))
                    print(f"Battery via UPower: {battery_level}% for {name}")
                    return battery_level
            
            # Method 3: Try dbus directly for bluetooth battery info
            dbus_cmd = f"dbus-send --system --print-reply --dest=org.bluez /org/bluez/hci0/dev_{mac.replace(':', '_')} org.freedesktop.DBus.Properties.Get string:org.bluez.Battery1 string:Percentage 2>/dev/null"
            dbus_output = self.run_bluetooth_command(dbus_cmd)
            if dbus_output:
                dbus_match = re.search(r'byte (\d+)', dbus_output)
                if dbus_match:
                    battery_level = int(dbus_match.group(1))
                    print(f"Battery via D-Bus: {battery_level}% for {name}")
                    return battery_level
            
            # Method 4: Try /sys/class/power_supply/ for bluetooth devices
            power_supply_output = self.run_bluetooth_command("find /sys/class/power_supply/ -name '*' -type d 2>/dev/null")
            for line in power_supply_output.split('\n'):
                if 'bluetooth' in line.lower() or mac.replace(':', '').lower() in line.lower():
                    capacity_file = f"{line}/capacity"
                    capacity_output = self.run_bluetooth_command(f"cat {capacity_file} 2>/dev/null")
                    if capacity_output.isdigit():
                        battery_level = int(capacity_output)
                        print(f"Battery via /sys: {battery_level}% for {name}")
                        return battery_level
            
            # Method 5: Check if it's a known audio device and try specific commands
            if any(word in name.lower() for word in ['headphone', 'headset', 'buds', 'airpods']):
                # Some devices report battery through custom commands
                custom_output = self.run_bluetooth_command(f"bluetoothctl info {mac} | grep -i battery")
                if custom_output:
                    numbers = re.findall(r'\d+', custom_output)
                    if numbers:
                        potential_battery = int(numbers[-1])  # Take the last number found
                        if 0 <= potential_battery <= 100:
                            print(f"Battery via custom parsing: {potential_battery}% for {name}")
                            return potential_battery
            
        except Exception as e:
            print(f"Error getting battery for {name} ({mac}): {e}")
        
        return None
    
    def scan_devices(self):
        """Start device scan"""
        if not self.bluetooth_enabled:
            return False
        
        self.command_queue.put("bluetoothctl scan on")
        # Stop scan after 5 seconds
        GLib.timeout_add_seconds(5, lambda: self.command_queue.put("bluetoothctl scan off"))
        
        return True  # Continue timer if it's a timer callback
    
    def on_bluetooth_toggled(self, switch, *args):
        """Handle bluetooth toggle"""
        if switch.get_active():
            self.command_queue.put("bluetoothctl power on")
        else:
            self.command_queue.put("bluetoothctl power off")
    
    def on_device_connect(self, device_info, connect=True):
        """Handle device connection/disconnection with loading indicator"""
        mac = device_info['mac']
        
        # Find the widget for this device and show loading
        widget = self.device_widgets.get(mac)
        if widget:
            widget.set_loading(True)
        
        if connect:
            self.command_queue.put(f"bluetoothctl connect {mac}")
        else:
            self.command_queue.put(f"bluetoothctl disconnect {mac}")
        
        # Update UI after a delay and hide loading
        def update_and_hide_loading():
            self.update_devices()
            if widget:
                widget.set_loading(False)
            return False
        
        GLib.timeout_add_seconds(3, update_and_hide_loading)
    
    def update_ui(self):
        """Update the UI with current devices"""
        # Clear existing content but preserve widget references
        child = self.content_box.get_first_child()
        while child:
            self.content_box.remove(child)
            child = self.content_box.get_first_child()
        
        self.device_widgets.clear()
        
        # Connected devices section
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
        
        # Available devices section
        if self.available_devices:
            if self.connected_devices:  # Add spacing if there were connected devices
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
        
        # Show message if no devices
        if not self.connected_devices and not self.available_devices:
            self.show_no_devices()
    
    def show_no_devices(self):
        """Show no devices available message"""
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
    
    def show_bluetooth_disabled(self):
        """Show bluetooth disabled message"""
        # Clear existing content
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