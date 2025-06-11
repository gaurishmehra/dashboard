How to use
===========
1. Clone the repository:
   ```bash
   git clone https://github.com/gaurishmehra/dashboard.git
   cd dashboard
    ```
    Install dunst and run it (Make sure no other notification daemon is running):
    ```bash
    sudo pacman -S dunst
    dunst &
    ```
2. Make the script executable:
   ```bash
   chmod +x dunst_log.py
   ```
3. Run the script:
   ```bash
    ./dunst_log.py &
   ```
   You should ideally put the script in the hyprland config or make a systemd service for it.
   ```bash
   exec-once = /path/to/dunst_log.py
   ```
4. Run the dashboard:
   ```bash
   python dashboard.py
   ```
5. (Optional) add the following lines to your hyprland config file:
   ```bash
    windowrulev2 = float, class:^(com.gaurish.Dashboard)$
    windowrulev2 = size 300 450, class:^(com.gaurish.Dashboard)$
    windowrulev2 = center, class:^(com.gaurish.Dashboard)$
    windowrulev2 = pin, class:^(com.gaurish.Dashboard)$
    windowrulev2 = noborder, class:^(com.gaurish.Dashboard)$
   ```
    I recommed making it a keybind to toggle the dashboard:
    ```bash
    #!/bin/bash

    # The full path to your media controller python script
    APP_SCRIPT="path/to/dashboard.py"

    # Check if the Media Controller window is open
    if hyprctl clients -j | jq -e '.[] | select(.title=="Media Controller")' > /dev/null 2>&1; then
        # If the window exists, close it by title
        hyprctl dispatch closewindow "title:^Media Controller$"
    else
        # If not running, launch it
        cd "path/to/dashboard" && python3 "$APP_SCRIPT" &
    fi
    ```
    Make it executable:
    ```bash
    chmod +x /path/to/your/script.sh
    ```
    Then link it to a keybind in your hyprland config (Ex - super + slash):
    ```bash
    bind = super, slash, exec, /path/to/your/script.sh
    ```

Current Features:
- Dunst notification logging
- Media controls
- Quick access ADB
- Wifi Controls
- Bluetooth Controls
- Weather Widget

Todo:
- Improve animations and overall UX
- Add the option to choose which widgets to display
- System monitoring widget (CPU, RAM, etc.)
- Session management widget (logout, switch user, etc.)

File Structure & Explanations
=============================

## Core Files

### `dashboard.py` - Main Application
The central hub of the application that manages the overall window and widget switching.

**Key Components:**
- **Dashboard Class**: Main window that holds the sidebar and content area
- **Sidebar Navigation**: Circular buttons for each widget (media, notifications, ADB, etc.)
- **Content Stack**: GTK Stack that switches between different widget views
- **Widget Lifecycle Management**: Only activates the currently visible widget to save resources
- **CSS Styling**: Comprehensive theming with glassmorphism effects, animations, and responsive design
- **Escape Key Handler**: Quick exit functionality

**Resource Optimization:**
- Widgets are created with a 50ms delay to prevent UI blocking on startup
- Only the active widget runs background processes (activate/deactivate pattern)
- Smooth transitions between views with 300ms slide animations

### `dunst_log.py` - Notification Logger
A sophisticated background service that monitors and logs all system notifications.

**Core Functionality:**
- **D-Bus Monitor**: Listens to `org.freedesktop.Notifications` interface
- **Real-time Parsing**: Processes notification data as it arrives
- **Image Extraction**: Extracts embedded images from notification data
- **Color Format Detection**: Automatically detects and corrects image color formats (RGB/BGR/RGBA/BGRA)
- **JSON Logging**: Stores notifications in structured format with metadata
- **File Rotation**: Automatically trims old notifications to prevent unlimited growth

**Image Processing Features:**
- Handles rowstride padding in image data
- Converts various color formats to standard PNG
- Debug mode saves images in all formats for troubleshooting
- Supports both embedded images and file path icons

**Usage:**
```bash
./dunst_log.py --debug    # Enable debug logging
./dunst_log.py --save-all-formats    # Save images in all color formats
```

## Widget Files

### `media_player.py` - Media Control Widget
Advanced media player controller using `playerctl` for system-wide media control.

**Key Features:**
- **Multi-Player Support**: Automatically detects and switches between media players
- **Circular Progress Bar**: Custom-drawn seek bar with click-to-seek functionality
- **Album Art Display**: Circular image widget with URL/file loading capabilities
- **Player Memory**: Remembers last used player between sessions
- **Background Commands**: Non-blocking command execution to prevent UI freezes

**Custom Widgets:**
- `CircularProgressWidget`: Interactive progress ring with Cairo drawing
- `CircularImage`: Cropped circular album art display
- `PlayerIconButton`: Smart icon detection for different media players

**Supported Players**: Spotify, VLC, Firefox, Chrome, Rhythmbox, and more

### `notifications.py` - Notification History Widget
Displays and manages notification history with search and interaction capabilities.

**Features:**
- **Live Updates**: Real-time monitoring of notification log file
- **Expandable Rows**: Click to expand/collapse notification details
- **Search Functionality**: Filter notifications by app name, summary, or body
- **Smart Icons**: Loads notification icons or shows app initial as fallback
- **Time Formatting**: Human-readable timestamps (now, 5m ago, yesterday, etc.)
- **Clear History**: Complete notification and image cache cleanup

**Performance Optimizations:**
- File monitoring with change detection
- Icons loaded as rows are created
- Efficient list filtering

### `wifi.py` - Network Management Widget
Comprehensive WiFi and Ethernet connection manager using NetworkManager.

**WiFi Features:**
- **Network Scanning**: Automatic and manual network discovery
- **Signal Strength**: Visual indicators and percentage display
- **Security Detection**: Shows network encryption status
- **Password Dialog**: Secure connection to protected networks
- **Connection Management**: Connect/disconnect with status feedback

**Ethernet Features:**
- **Wired Connections**: Manage Ethernet/LAN connections
- **Device Detection**: Automatic network device discovery
- **Connection Profiles**: Manage saved network configurations

**Background Processing:**
- Command queue system prevents UI blocking
- Periodic network status updates
- Connection state monitoring

### `bluetooth.py` - Bluetooth Device Manager
Full-featured Bluetooth device management with advanced battery monitoring.

**Device Management:**
- **Device Discovery**: Scan for nearby devices and connect to paired ones
- **Smart Icons**: Automatic device type detection (headphones, mouse, keyboard, etc.)
- **Connection Control**: Easy connect/disconnect with visual feedback
- **Device Classification**: Automatic categorization based on device properties

**Battery Monitoring:**
- Multiple detection methods for maximum compatibility
- Support for various battery reporting standards
- Real-time battery level updates for connected devices

**Advanced Features:**
- Device type detection via Bluetooth class codes
- Background scanning and connection management
- Functional error handling and basic logging

### `adb.py` - Android Debug Bridge Controller
Professional ADB device management for Android developers and power users.

**Device Management:**
- **Multi-Device Support**: Handle multiple connected Android devices
- **Device Information**: Model, Android version, battery level display
- **Visual Selection**: Circular device buttons for easy switching

**Quick Actions Grid:**
- Lock/Wake Screen
- Home/Back/Recent Apps navigation
- Device reboot functionality
- Extensible action system

**Safety Features:**
- Background command execution
- Device state monitoring
- Standard error handling

### `weather.py` - Weather Information Widget
Beautiful weather display with current conditions and forecasts.

**Data Sources:**
- **Open-Meteo API**: Free weather data service
- **Reverse Geocoding**: Automatic location name resolution
- **Configuration**: Latitude/longitude from `.env` file

**Display Features:**
- **Current Weather**: Temperature, conditions, feels-like, humidity, wind
- **24-Hour Forecast**: Scrollable hourly predictions with precipitation
- **7-Day Forecast**: Daily high/low temperatures and conditions
- **Weather Icons**: Symbolic icons matching system theme

**Performance:**
- Data fetching scheduled on the main GTK thread
- Periodic updates (10-minute intervals)

## Configuration Files

### `.env` - Environment Configuration
Simple configuration file for location-based services:
```
LATITUDE=40.7128
LONGITUDE=-74.0060
```

## Dependencies & Requirements

**System Requirements:**
- GTK 4.0+ and Adwaita library
- Python 3.8+
- NetworkManager (for WiFi/Ethernet)
- Bluetooth stack (bluez)
- playerctl (for media control)
- ADB tools (for Android debugging)
- dunst (notification daemon)

**Python Packages:**
- PyGObject (GTK bindings)
- Pillow (image processing)
- numpy (numerical operations)
- requests (HTTP requests)

## Architecture & Design Patterns

### Widget Lifecycle Pattern
Each widget implements `activate()`/`deactivate()` methods:
- **Activate**: Start background processes, timers, and monitoring
- **Deactivate**: Stop all background activity to save resources

### Command Queue Pattern
Background command execution prevents UI freezing:
- Commands queued from UI thread
- Executed in dedicated worker thread
- Results processed on main thread when needed

### Resource Management
- File monitoring with automatic cleanup
- Image caching with size limits
- Periodic data updates only when widget is visible
- Memory-efficient list operations

This modular architecture ensures each component can operate independently while maintaining consistent UI patterns and resource efficiency throughout the application.