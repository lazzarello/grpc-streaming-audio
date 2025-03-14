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
        self.audio_event_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.mode = 0
        self.recording = False
        self.audio_filenames = ["startup_mode.wav",
                                 "mode_1.wav", 
                                 "mode_2.wav", 
                                 "mode_3.wav", 
                                 "mode_4.wav", 
                                 "mode_5.wav"]
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
        status_set = self.device_status_set(self.leds)
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        self.audio_event_queue.put({"play": True})
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_mode_event(self, event):
        # Ignore LED 0, cycle through LEDs 1-5
        # First, check if any LED is currently on
        active_led = -1
        for i in range(1, 6):
            if self.leds[i] != 0x00000000:
                active_led = i
                break
        
        # Turn off the active LED if there is one
        if active_led != -1:
            self.leds[active_led] = 0x00000000
            
        # Turn on the next LED in sequence (with wraparound)
        next_led = 1 if active_led == 5 or active_led == -1 else active_led + 1
        self.leds[next_led] = 0xFF00FFFF  # Magenta color
        self.mode = next_led
        print(f"Device is in mode {self.mode}")
        
        print(f"LED {next_led} is now on: {hex(self.leds[next_led])}")
        status_set = self.device_status_set(self.leds)
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_stop_event(self, event):
        # Set all LEDs to off (0x00000000)
        self.leds = [0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000]
        print(f"All LEDs turned off")
        status_set = self.device_status_set(self.leds)
        self.mode = 0
        self.audio_event_queue.put({"play": False})
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled stop event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_power_event(self, event):
        print(f"DeviceManager handled power event {repr(event)}")

    def handle_status_request(self, request, context):
        if request.kind() == "get":
            print("Get Device status")
            return request
        elif request.kind() == "set":
            print("Set Device status")
            return request.set