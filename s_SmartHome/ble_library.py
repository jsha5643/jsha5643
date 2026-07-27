import bluetooth
import struct
import time

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3

_FLAG_WRITE = 8
_FLAG_NOTIFY = 16

# Nordic UART Service (NUS) UUIDs
_UART_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
_UART_TX = (
    bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e"),
    _FLAG_NOTIFY,
)
_UART_RX = (
    bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e"),
    _FLAG_WRITE,
)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX))

# Helper to generate advertising payload discoverable by mobile browsers
def advertising_payload(limited_discoverable=False, brz=False, name=None, services=None, appearance=0):
    payload = bytearray()

    def append(adv_type, value):
        nonlocal payload
        payload.append(len(value) + 1)
        payload.append(adv_type)
        payload.extend(value)

    # Flag
    append(0x01, struct.pack("B", (0x01 if limited_discoverable else 0x02) | (0x18 if brz else 0x00)))

    # Name
    if name:
        append(0x09, name.encode("utf-8"))

    # Services
    if services:
        for uuid in services:
            b = bytes(uuid)
            if len(b) == 2:
                append(0x03, b)
            elif len(b) == 16:
                append(0x07, b)

    # Appearance
    if appearance:
        append(0x19, struct.pack("<H", appearance))

    return payload

class BLESimplePeripheral:
    def __init__(self, ble, name="ESP_Js"):
        self._ble = ble
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((_UART_SERVICE,))
        self._connections = set()
        self._write_callback = None
        self._payload = advertising_payload(name=name, services=[_UART_UUID])
        self._advertise()

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            print("BLE Connected:", conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            if conn_handle in self._connections:
                self._connections.remove(conn_handle)
            print("BLE Disconnected:", conn_handle)
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle == self._handle_rx:
                value = self._ble.gatts_read(self._handle_rx)
                if self._write_callback:
                    self._write_callback(value)

    def on_write(self, callback):
        self._write_callback = callback

    def send(self, data):
        # Convert string to bytes if necessary
        if isinstance(data, str):
            data = data.encode('utf-8')
        for conn_handle in self._connections:
            self._ble.gatts_write(self._handle_tx, data)
            self._ble.gatts_notify(conn_handle, self._handle_tx)

    def _advertise(self, interval_us=500000):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)
        print("BLE Advertising...")
