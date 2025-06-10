import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gio
import subprocess
import json
import threading
import queue
import warnings
import re

warnings.filterwarnings("ignore")

class DeviceInfoWidget(Gtk.Box):
    def __init__(self, device_info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.device_info = device_info
        self.create_ui()
    
    def create_ui(self):
        # Device header card
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header_card.add_css_class("device-header")
        header_card.set_margin_top(16)
        header_card.set_margin_bottom(16)
        header_card.set_margin_start(20)
        header_card.set_margin_end(20)
        
        # Device icon
        device_icon = Gtk.Image()
        device_icon.set_from_icon_name("phone-symbolic")
        device_icon.set_pixel_size(40)
        device_icon.add_css_class("device-icon")
        
        # Device info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        device_name = self.device_info.get('model', 'Unknown Device')
        name_label = Gtk.Label(label=device_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        
        device_id = self.device_info.get('device_id', 'Unknown')
        id_label = Gtk.Label(label=f"ID: {device_id}")
        id_label.set_halign(Gtk.Align.START)
        id_label.add_css_class("device-id")
        
        info_box.append(name_label)
        info_box.append(id_label)
        
        header_card.append(device_icon)
        header_card.append(info_box)
        
        # Info tiles grid
        tiles_grid = Gtk.Grid()
        tiles_grid.set_row_spacing(12)
        tiles_grid.set_column_spacing(12)
        tiles_grid.set_halign(Gtk.Align.CENTER)
        tiles_grid.set_margin_start(20)
        tiles_grid.set_margin_end(20)
        
        # Android version tile
        android_version = self.device_info.get('android_version', 'Unknown')
        android_tile = self.create_info_tile("Android", android_version, "computer-symbolic")
        tiles_grid.attach(android_tile, 0, 0, 1, 1)
        
        # Battery level tile
        battery_level = self.device_info.get('battery_level', 'Unknown')
        battery_tile = self.create_info_tile("Battery", battery_level, "battery-good-symbolic")
        tiles_grid.attach(battery_tile, 1, 0, 1, 1)
        
        self.append(header_card)
        self.append(tiles_grid)
    
    def create_info_tile(self, title, value, icon_name):
        """Create an aesthetic info tile"""
        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tile.add_css_class("info-tile")
        tile.set_size_request(140, 80)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        icon.add_css_class("tile-icon")
        
        # Title
        title_label = Gtk.Label(label=title)
        title_label.add_css_class("tile-title")
        
        # Value
        value_label = Gtk.Label(label=value)
        value_label.add_css_class("tile-value")
        value_label.set_ellipsize(Pango.EllipsizeMode.END)
        value_label.set_max_width_chars(12)
        
        tile.append(icon)
        tile.append(title_label)
        tile.append(value_label)
        
        return tile

class QuickActionsWidget(Gtk.Box):
    def __init__(self, device_id, command_callback):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.device_id = device_id
        self.command_callback = command_callback
        self.create_ui()
    
    def create_ui(self):
        # Quick actions header
        actions_label = Gtk.Label(label="Quick Actions")
        actions_label.add_css_class("section-title")
        actions_label.set_halign(Gtk.Align.CENTER)
        actions_label.set_margin_top(16)
        actions_label.set_margin_start(20)
        
        # Action buttons grid
        actions_grid = Gtk.Grid()
        actions_grid.set_row_spacing(8)
        actions_grid.set_column_spacing(8)
        actions_grid.set_margin_start(16)
        actions_grid.set_margin_end(16)
        actions_grid.set_halign(Gtk.Align.CENTER)
        
        # Define actions
        actions = [
            ("Lock Screen", "changes-prevent-symbolic", "input keyevent 26"),
            ("Wake Screen", "changes-allow-symbolic", "input keyevent 82"),
            ("Home", "go-home-symbolic", "input keyevent 3"),
            ("Back", "go-previous-symbolic", "input keyevent 4"),
            ("Recent Apps", "view-grid-symbolic", "input keyevent 187"),
            ("Restart", "view-refresh-symbolic", "reboot"),
        ]
        
        # Create action buttons
        for i, (name, icon, command) in enumerate(actions):
            button = Gtk.Button()
            button.set_size_request(120, 80)
            button.add_css_class("action-button")
            
            # Button content
            button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            
            button_icon = Gtk.Image.new_from_icon_name(icon)
            button_icon.set_pixel_size(24)
            
            button_label = Gtk.Label(label=name)
            button_label.add_css_class("action-label")
            button_label.set_wrap(True)
            button_label.set_justify(Gtk.Justification.CENTER)
            
            button_box.append(button_icon)
            button_box.append(button_label)
            button.set_child(button_box)
            
            # Connect click handler
            button.connect("clicked", lambda b, cmd=command: self.command_callback(self.device_id, cmd))
            
            # Position in grid (3 columns for better fit)
            row = i // 3
            col = i % 3
            actions_grid.attach(button, col, row, 1, 1)
        
        self.append(actions_label)
        self.append(actions_grid)

class DeviceButton(Gtk.Button):
    def __init__(self, device_info):
        super().__init__()
        self.device_info = device_info
        self.set_size_request(48, 48)
        self.add_css_class("circular")
        self.add_css_class("flat")
        self.add_css_class("player-icon")
        
        # Use phone icon for all devices
        self.set_icon_name("phone-symbolic")
        
        # Tooltip with device info
        device_name = device_info.get('model', 'Unknown Device')
        device_id = device_info.get('device_id', 'Unknown')
        self.set_tooltip_text(f"{device_name}\nID: {device_id}")
    
    def set_active(self, active):
        if active:
            self.add_css_class("suggested-action")
        else:
            self.remove_css_class("suggested-action")

class ADBWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.devices = []
        self.current_device = None
        self.device_buttons = []
        
        # Command queue for async execution
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        
        # **LAG FIX: Properties to manage activation state**
        self.is_active = False
        self.update_timer_id = None
        
        self.create_ui()
        
        # **LAG FIX: Don't start monitoring immediately. This is now handled by activate().**
    
    # **LAG FIX: New methods to control background activity**
    def activate(self):
        """Called when the widget becomes visible."""
        if self.is_active:
            return
        self.is_active = True
        print("ADBWidget Activated")
        self.update_devices() # Initial update
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(3, self.update_devices)

    def deactivate(self):
        """Called when the widget is hidden."""
        if not self.is_active:
            return
        self.is_active = False
        print("ADBWidget Deactivated")
        if self.update_timer_id:
            GLib.source_remove(self.update_timer_id)
            self.update_timer_id = None

    def command_worker(self):
        """Worker thread for executing ADB commands"""
        while True:
            try:
                device_id, command = self.command_queue.get(timeout=1)
                if device_id and command:
                    # Differentiate between shell and non-shell commands
                    if command.startswith("reboot"):
                        full_command = f"adb -s {device_id} {command}"
                    else:
                        full_command = f"adb -s {device_id} shell {command}"
                    
                    result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        print(f"ADB command failed: {full_command}")
                        print(f"Error: {result.stderr}")
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"ADB command error: {e}")
    
    def create_ui(self):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        
        # Device selection row
        self.devices_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.devices_box.set_halign(Gtk.Align.CENTER)
        
        # Scrollable content
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        scrolled_window.add_css_class("invisible-scroll")
        
        # Content container
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_start(8)
        self.content_box.set_margin_end(8)
        self.content_box.set_margin_bottom(16)
        
        scrolled_window.set_child(self.content_box)
        
        self.append(self.devices_box)
        self.append(scrolled_window)
    
    def run_adb_command(self, command):
        """Run ADB command and return output"""
        try:
            result = subprocess.run(f"adb {command}", shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"ADB command error: {e}")
            return ""
    
    def get_device_info(self, device_id):
        """Get detailed device information"""
        info = {'device_id': device_id}
        
        try:
            # Get device model
            model = self.run_adb_command(f"-s {device_id} shell getprop ro.product.model")
            info['model'] = model or "Unknown Device"
            
            # Get Android version
            android_version = self.run_adb_command(f"-s {device_id} shell getprop ro.build.version.release")
            info['android_version'] = android_version or "Unknown"
            
            # Get battery level
            battery_output = self.run_adb_command(f"-s {device_id} shell dumpsys battery")
            battery_match = re.search(r'level: (\d+)', battery_output)
            battery_level = battery_match.group(1) if battery_match else "Unknown"
            info['battery_level'] = f"{battery_level}%" if battery_level != "Unknown" else "Unknown"
            
            info['state'] = 'device'
            
        except Exception as e:
            print(f"Error getting device info for {device_id}: {e}")
            info.update({
                'model': 'Unknown Device',
                'android_version': 'Unknown',
                'battery_level': 'Unknown',
                'state': 'unknown'
            })
        
        return info
    
    def update_devices(self):
        """Update list of connected devices"""
        # **LAG FIX: Add a guard to ensure it only runs when active.**
        if not self.is_active:
            return False # Stop the timer

        devices_output = self.run_adb_command("devices")
        
        new_device_infos = []
        if devices_output:
            lines = devices_output.split('\n')[1:]
            for line in lines:
                if line.strip() and '\t' in line:
                    device_id, state = line.strip().split('\t')
                    if state == 'device':
                        device_info = self.get_device_info(device_id)
                        new_device_infos.append(device_info)
        
        # Check for changes more reliably
        current_ids = {d['device_id'] for d in self.devices}
        new_ids = {d['device_id'] for d in new_device_infos}

        if current_ids != new_ids:
            self.devices = new_device_infos
            self.update_device_buttons()
            self.update_ui()
        
        return True # Continue timer
    
    def update_device_buttons(self):
        """Update device selection buttons"""
        for button in self.device_buttons:
            self.devices_box.remove(button)
        self.device_buttons.clear()
        
        if self.devices:
            for device_info in self.devices:
                button = DeviceButton(device_info)
                button.connect("clicked", lambda b, d=device_info: self.on_device_selected(d))
                self.device_buttons.append(button)
                self.devices_box.append(button)
            
            # Select first device if none selected or if current is disconnected
            current_device_still_connected = self.current_device and any(d['device_id'] == self.current_device['device_id'] for d in self.devices)
            if not current_device_still_connected and self.devices:
                self.current_device = self.devices[0]
            
            self.update_button_states()
    
    def update_button_states(self):
        """Update visual state of device buttons"""
        for i, button in enumerate(self.device_buttons):
            if i < len(self.devices):
                is_current = (self.devices[i]['device_id'] == 
                             self.current_device['device_id'] if self.current_device else False)
                button.set_active(is_current)
    
    def on_device_selected(self, device_info):
        """Handle device selection"""
        self.current_device = device_info
        self.update_button_states()
        self.update_ui()
    
    def update_ui(self):
        """Update the UI with current device"""
        child = self.content_box.get_first_child()
        while child:
            self.content_box.remove(child)
            child = self.content_box.get_first_child()
        
        if not self.devices:
            self.show_no_devices()
            return
        
        if not self.current_device:
            # This case shouldn't happen if devices exist, but as a fallback
            self.show_no_devices()
            return
        
        device_widget = DeviceInfoWidget(self.current_device)
        self.content_box.append(device_widget)
        
        actions_widget = QuickActionsWidget(self.current_device['device_id'], self.execute_command)
        self.content_box.append(actions_widget)
    
    def show_no_devices(self):
        """Show no devices state"""
        no_devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        no_devices_box.set_valign(Gtk.Align.CENTER)
        no_devices_box.set_vexpand(True)
        
        icon = Gtk.Image.new_from_icon_name("phone-disabled-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        
        message_label = Gtk.Label(label="No ADB Devices Connected")
        message_label.add_css_class("title-large")
        message_label.add_css_class("dim-label")
        
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        instructions_box.set_halign(Gtk.Align.CENTER)
        
        instructions = [
            "1. Enable Developer Options on your device.",
            "2. Enable USB Debugging in Developer Options.",
            "3. Connect your device via USB or Wi-Fi.",
            "4. Authorize the debugging connection on your device."
        ]
        
        for instruction in instructions:
            inst_label = Gtk.Label(label=instruction)
            inst_label.add_css_class("dim-label")
            instructions_box.append(inst_label)
        
        no_devices_box.append(icon)
        no_devices_box.append(message_label)
        no_devices_box.append(instructions_box)
        
        self.content_box.append(no_devices_box)
    
    def execute_command(self, device_id, command):
        """Queue an ADB command for execution"""
        if device_id and command:
            self.command_queue.put((device_id, command))