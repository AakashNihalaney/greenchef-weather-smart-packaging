"""
p2l_controller.py — Pick-to-Light Hardware Coordination Layer
Sends flash signals to bin lights via MQTT (real) or simulated (mock).
Protocol: MQTT topic  packing/floor/{bin_id}/flash  payload: {"count": N}
"""

import json
import time
import threading
from datetime import datetime
from typing import Optional
from database import log, log_p2l_event

# Optional MQTT support
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

MQTT_BROKER   = "localhost"
MQTT_PORT     = 1883
MQTT_TOPIC_BASE = "packing/floor"

# Modbus optional
try:
    from pymodbus.client import ModbusTcpClient
    MODBUS_AVAILABLE = True
except ImportError:
    MODBUS_AVAILABLE = False

MODBUS_HOST = "192.168.1.100"
MODBUS_PORT = 502


class P2LStatus:
    """Shared mutable state for the UI status indicator."""
    def __init__(self):
        self.active       = False
        self.current_bin  = ""
        self.current_item = ""
        self.flash_queue: list[dict] = []
        self.completed:   list[dict] = []
        self.error_msg    = ""
        self._lock        = threading.Lock()

    def set_active(self, bin_id: str, item: str):
        with self._lock:
            self.active       = True
            self.current_bin  = bin_id
            self.current_item = item

    def set_idle(self):
        with self._lock:
            self.active       = False
            self.current_bin  = ""
            self.current_item = ""

    def add_completed(self, event: dict):
        with self._lock:
            self.completed.append(event)

    def reset(self):
        with self._lock:
            self.active       = False
            self.current_bin  = ""
            self.current_item = ""
            self.flash_queue  = []
            self.completed    = []
            self.error_msg    = ""


# Singleton status for Streamlit to read
p2l_status = P2LStatus()


class P2LController:
    """
    Coordinates Pick-to-Light signals for a packing manifest.
    Supports: MQTT (preferred), Modbus TCP, or simulated mode.
    """

    def __init__(self, protocol: str = "simulated"):
        self.protocol = protocol
        self._mqtt_client: Optional[object] = None
        self._modbus_client: Optional[object] = None
        self._connected = False

        if protocol == "mqtt" and MQTT_AVAILABLE:
            self._init_mqtt()
        elif protocol == "modbus" and MODBUS_AVAILABLE:
            self._init_modbus()
        else:
            self.protocol = "simulated"
            log("INFO", "p2l_controller",
                "Running in SIMULATED mode — no physical P2L hardware required.")

    # ── Init ──────────────────────────────────────────────────────────────────

    def _init_mqtt(self):
        try:
            self._mqtt_client = mqtt.Client(client_id="p2l_fulfillment")
            self._mqtt_client.on_connect    = self._on_mqtt_connect
            self._mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self._mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self._mqtt_client.loop_start()
            self._connected = True
            log("INFO", "p2l_controller", f"MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
        except Exception as e:
            log("ERROR", "p2l_controller", f"MQTT init failed: {e}. Falling back to simulated.")
            self.protocol = "simulated"

    def _init_modbus(self):
        try:
            self._modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
            if self._modbus_client.connect():
                self._connected = True
                log("INFO", "p2l_controller", f"Modbus TCP connected to {MODBUS_HOST}:{MODBUS_PORT}")
            else:
                raise ConnectionError("Modbus connect() returned False")
        except Exception as e:
            log("ERROR", "p2l_controller", f"Modbus init failed: {e}. Falling back to simulated.")
            self.protocol = "simulated"

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        log("INFO", "p2l_controller", f"MQTT on_connect rc={rc}")
        self._connected = (rc == 0)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        self._connected = False
        log("WARNING", "p2l_controller", f"MQTT disconnected rc={rc}")

    # ── Signal Dispatch ───────────────────────────────────────────────────────

    def _send_signal(self, bin_id: str, flash_count: int, color: str = "GREEN") -> bool:
        payload = json.dumps({
            "bin_id":      bin_id,
            "flash_count": flash_count,
            "color":       color,
            "ts":          datetime.now().isoformat(),
        })

        if self.protocol == "mqtt" and self._connected:
            topic = f"{MQTT_TOPIC_BASE}/{bin_id}/flash"
            result = self._mqtt_client.publish(topic, payload)
            return result.rc == 0

        elif self.protocol == "modbus" and self._connected:
            # Map bin_id → Modbus register address (example mapping)
            reg = self._bin_to_modbus_register(bin_id)
            self._modbus_client.write_register(reg, flash_count)
            return True

        else:
            # Simulated: print signal, add tiny delay to mimic hardware
            log("INFO", "p2l_controller",
                f"[SIM] BIN {bin_id} → {flash_count}x flash ({color}) | payload: {payload}")
            time.sleep(0.05)
            return True

    def _bin_to_modbus_register(self, bin_id: str) -> int:
        """Map BIN-XX → Modbus holding register index."""
        mapping = {
            "BIN-A1": 100, "BIN-A2": 101,
            "BIN-B1": 102, "BIN-B2": 103,
            "BIN-C1": 104, "BIN-C2": 105,
            "BIN-D1": 106, "BIN-D2": 107,
        }
        return mapping.get(bin_id, 200)

    # ── Public API ────────────────────────────────────────────────────────────

    def signal_manifest(self, manifest: dict) -> list[dict]:
        """
        For every item in the manifest, flash the corresponding bin light
        exactly `qty` times. Returns list of P2L event records.
        """
        order_id = manifest["order_id"]
        events   = []
        p2l_status.reset()

        all_items = manifest.get("meal_items", []) + manifest.get("packaging", [])
        p2l_status.flash_queue = [i.get("name", "?") for i in all_items]

        for item in all_items:
            name   = item.get("name", "Unknown")
            qty    = item.get("qty", 1)
            bin_id = item.get("bin_id", "BIN-UNKNOWN")

            if bin_id == "BIN-UNKNOWN":
                log("WARNING", "p2l_controller",
                    f"No bin mapping for item '{name}' in order {order_id}")
                continue

            p2l_status.set_active(bin_id, name)

            success = self._send_signal(bin_id, qty)
            event = {
                "order_id":    order_id,
                "bin_id":      bin_id,
                "item_name":   name,
                "flash_count": qty,
                "success":     success,
                "triggered_at": datetime.now().isoformat(),
            }
            events.append(event)
            p2l_status.add_completed(event)
            log_p2l_event(order_id, bin_id, name, qty)

            if not success:
                log("ERROR", "p2l_controller",
                    f"Signal failed for {bin_id} ({name} x{qty})")
                p2l_status.error_msg = f"Signal error: {bin_id} — {name}"

            time.sleep(0.1)  # inter-signal delay

        p2l_status.set_idle()
        log("INFO", "p2l_controller",
            f"P2L sequence complete for {order_id}: {len(events)} bins signaled.")
        return events

    def flash_alert(self, bin_id: str = "BIN-ALL", color: str = "RED"):
        """Send a red alert flash to all bins (weight error, etc.)."""
        self._send_signal(bin_id, flash_count=5, color=color)
        log("ERROR", "p2l_controller", f"RED ALERT flashed on {bin_id}")

    def is_connected(self) -> bool:
        if self.protocol == "simulated":
            return True
        return self._connected

    def get_protocol_label(self) -> str:
        labels = {
            "mqtt":      "MQTT (Live)",
            "modbus":    "Modbus TCP (Live)",
            "simulated": "Simulated",
        }
        return labels.get(self.protocol, self.protocol)

    def disconnect(self):
        if self.protocol == "mqtt" and self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
        elif self.protocol == "modbus" and self._modbus_client:
            self._modbus_client.close()
