import queue
from google.protobuf import text_format
import comms_pb2

class DeviceManager():
    '''
    map device status from the status stream to this class, and change the state in the instance of this class
    '''
    def __init__(self):
        self.device_id = None
        self.state = None
        self.leds = [0x00000000
                     ,0x00000000
                     ,0x00000000
                     ,0x00000000
                     ,0x00000000
                     ,0x00000000]
        self.event_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.mode = 0
        self.recording = False
        self.audio_frames = []
        self.stream = None

    def device_status_set(self, leds):
        """Create a DeviceStatusSet message from a list of LED values."""
        return comms_pb2.DeviceStatusSet(
            led_0=comms_pb2.RGBAColor(rgba=leds[0]),
            led_1=comms_pb2.RGBAColor(rgba=leds[1]),
            led_2=comms_pb2.RGBAColor(rgba=leds[2]),
            led_3=comms_pb2.RGBAColor(rgba=leds[3]),
            led_4=comms_pb2.RGBAColor(rgba=leds[4]),
            led_5=comms_pb2.RGBAColor(rgba=leds[5])
        )

    def handle_play_event(self, event):
        self.leds[2] = 0xFFFF00FF if self.leds[2] == 0x00000000 else 0x00000000
        print(f"Led 2 is {hex(self.leds[2])}")
        status_set = self.device_status_set(self.leds)
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_mode_event(self, event):
        self.leds[3] = 0xFF00FFFF if self.leds[3] == 0x00000000 else 0x00000000
        print(f"Led 3 is {hex(self.leds[3])}")
        status_set = self.device_status_set(self.leds)
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_stop_event(self, event):
        self.leds[1] = 0x01FFFFFF if self.leds[1] == 0x00000000 else 0x00000000
        print(f"Led 1 is {hex(self.leds[1])}")
        status_set = self.device_status_set(self.leds)
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_power_event(self, event):
        print(f"DeviceManager handled power event {repr(event)}")

    def handle_status_request(self, request, context):
        if request.kind() == "get":
            print("Get Device status")
            return request
        elif request.kind() == "set":
            print("Set Device status")
            return request.set