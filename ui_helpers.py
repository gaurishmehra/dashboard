import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk


STACK_TRANSITION_MS = 140
REVEALER_TRANSITION_MS = 140


def configure_stack_transition(stack: Gtk.Stack) -> None:
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    stack.set_transition_duration(STACK_TRANSITION_MS)


# Shared pink-toggle switch CSS — single source of truth for wifi.py and bluetooth.py
_PINK_SWITCH_CSS_APPLIED = False

def ensure_pink_switch_css():
    """Apply pink-themed switch CSS exactly once across all modules."""
    global _PINK_SWITCH_CSS_APPLIED
    if _PINK_SWITCH_CSS_APPLIED:
        return
    css = """
    switch.pink-toggle {
        background-color: rgba(255, 182, 193, 0.25);
        border: 1px solid rgba(255, 182, 193, 0.4);
        transition: all 150ms ease;
    }
    switch.pink-toggle:hover {
        background-color: rgba(255, 182, 193, 0.35);
        border-color: rgba(255, 182, 193, 0.5);
    }
    switch.pink-toggle slider {
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 1px 2px rgba(0,0,0,0.25);
    }
    switch.pink-toggle:checked {
        background-color: rgba(255, 182, 193, 0.5);
        border-color: rgba(255, 182, 193, 0.7);
        box-shadow: 0 0 0 3px rgba(255, 182, 193, 0.2);
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _PINK_SWITCH_CSS_APPLIED = True


def build_status_widget(
    title: str,
    subtitle: str = "",
    icon_name: str = "",
    spinner: bool = False,
) -> Gtk.Box:
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=12,
        halign=Gtk.Align.CENTER,
        valign=Gtk.Align.CENTER,
        vexpand=True,
    )

    if spinner:
        indicator = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
        box.append(indicator)
    elif icon_name:
        icon = Gtk.Image(icon_name=icon_name)
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        box.append(icon)

    title_label = Gtk.Label(label=title, css_classes=["title-label"])
    box.append(title_label)

    if subtitle:
        subtitle_label = Gtk.Label(label=subtitle, css_classes=["dim-label"])
        subtitle_label.set_justify(Gtk.Justification.CENTER)
        subtitle_label.set_wrap(True)
        box.append(subtitle_label)

    return box
