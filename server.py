from concurrent import futures
import logging
import grpc
import comms_pb2
import comms_pb2_grpc
import queue
from google.protobuf import text_format

# import audio # might not need this

# is this the right place to queue up messages? Might only need two, not three
device_state_queue = queue.Queue()
events_queue = queue.Queue()
device_playback_queue = queue.Queue()
devices_states = {}
sound_filename = 'playback.opus'
sound_buffer = open(sound_filename, 'rb')

'''
Handle both device state in a loop that looks for the queue and audio stream through manager classes
'''
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

    def handle_play_event(self, event):
        self.leds[2] = 0xFFFF00FF if self.leds[2] == 0x00000000 else 0x00000000
        print(f"Led 2 is {hex(self.leds[2])}")
        status_set = comms_pb2.DeviceStatusSet(
            led_0=comms_pb2.RGBAColor(rgba=self.leds[0]),
            led_1=comms_pb2.RGBAColor(rgba=self.leds[1]),
            led_2=comms_pb2.RGBAColor(rgba=self.leds[2]),
            led_3=comms_pb2.RGBAColor(rgba=self.leds[3]),
            led_4=comms_pb2.RGBAColor(rgba=self.leds[4]),
            led_5=comms_pb2.RGBAColor(rgba=self.leds[5]),
        )
        # Put the status set request in the status queue
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_mode_event(self, event):
        # Toggle LED 3 (index 3) between off (0x00000000) and on (0xFFFFFFFF)
        self.leds[3] = 0xFF00FFFF if self.leds[3] == 0x00000000 else 0x00000000
        print(f"Led 3 is {hex(self.leds[3])}")

        '''
        # interesting...this doesn't really do much but might because...protos?
        status_set = comms_pb2.DeviceStatusSet()
        status_set.led_3.SetInParent()
        status_set.led_3.rgba = self.leds[3]
        '''
        # the contents of event are the button event, so it doesn't really matter to pass it here.
        # it's helpful for debugging tho
        # Create a status set request with the updated LED state
        status_set = comms_pb2.DeviceStatusSet(
            led_0=comms_pb2.RGBAColor(rgba=self.leds[0]),
            led_1=comms_pb2.RGBAColor(rgba=self.leds[1]),
            led_2=comms_pb2.RGBAColor(rgba=self.leds[2]),
            led_3=comms_pb2.RGBAColor(rgba=self.leds[3]),
            led_4=comms_pb2.RGBAColor(rgba=self.leds[4]),
            led_5=comms_pb2.RGBAColor(rgba=self.leds[5]),
        )
        # Put the status set request in the status queue
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_stop_event(self, event):
        self.leds[1] = 0x01FFFFFF if self.leds[1] == 0x00000000 else 0x00000000
        print(f"Led 1 is {hex(self.leds[1])}")
        # I guess wrap this in some kind of logic for the status request type?
        status_set = comms_pb2.DeviceStatusSet(
            led_0=comms_pb2.RGBAColor(rgba=self.leds[0]),
            led_1=comms_pb2.RGBAColor(rgba=self.leds[1]),
            led_2=comms_pb2.RGBAColor(rgba=self.leds[2]),
            led_3=comms_pb2.RGBAColor(rgba=self.leds[3]),
            led_4=comms_pb2.RGBAColor(rgba=self.leds[4]),
            led_5=comms_pb2.RGBAColor(rgba=self.leds[5]),
        )
        # Put the status set request in the status queue
        self.status_queue.put(comms_pb2.DeviceStatusRequest(set=status_set))
        print(f"DeviceManager handled mode event {repr(event)}, set device state to {text_format.MessageToString(status_set)}")

    def handle_power_event(self, event):
        print(f"DeviceManager handled power event {repr(event)}")

    # do I even need this? aren't I just doing this over the status_queue?
    def handle_status_request(self, request, context):
        if request.kind() == "get":
            print("Get Device status")
            # send status GET request
            return request
        elif request.kind() == "set":
            print("Set Device status")
            # send status SET request
            return request.set

    def device_status_set(self, leds):
        return comms_pb2.DeviceStatusSet(
            led_0=comms_pb2.RGBAColor(rgba=leds[0]),
            led_1=comms_pb2.RGBAColor(rgba=leds[1]),
            led_2=comms_pb2.RGBAColor(rgba=leds[2]),
            led_3=comms_pb2.RGBAColor(rgba=leds[3]),
            led_4=comms_pb2.RGBAColor(rgba=leds[4]),
            led_5=comms_pb2.RGBAColor(rgba=leds[5]),
        )

# can't wait to get to this part
class AudioStreamManager():
    def __init__(self, device_id):
        self.device_id = device_id
        self.state = comms_pb2.DeviceStatus

class DeviceServiceServicer(comms_pb2_grpc.DeviceServiceServicer):
    def __init__(self):
        self.device_manager = DeviceManager() # TODO: get id from metadata in client...

    def StatusStream(self, request_iterator, context):
        '''
        Handle device status requests from the client, and return the device status.
        Device connects and listens, send something immediately.
        Set state immediately from DeviceManager to set the status from output proto.
        '''
        print("Server received status request from client")
        status_set = self.device_manager.device_status_set(self.device_manager.leds)
        yield comms_pb2.DeviceStatusRequest(set=status_set)

        # for status_response in request_iterator:
        #     print(f"Server received status response: {status_response}")
        #     yield comms_pb2.DeviceStatusRequest()
        for request in request_iterator:
            # Maybe look for "error" and handle that as an exception?
            print(f"Server received request status: {request}")
            try:
                event = self.device_manager.status_queue.get()  # 1 second timeout
                # this yield is required as it the first yield because the client needs a response to stop asking if it is connected.
                yield event
                # perhaps some logic here to handle the GET versus SET logic?
                # right now I'm assuming only SET from button events.
            # except queue.Empty:
            #     print(f"Status queue empty. Waiting... ")
            #     continue
            except grpc.RpcError as e:
                print(f"RPC error in StatusStream: {e}")
            except Exception as e:
                print(f"Error in StatusStream: {e}")

    def EventStream(self, request_iterator, context):
        '''
        When the client and server have acknowledged the event, return an ack, then loop over the request_iterator for events.
        '''
        try:
            for request in request_iterator:
                print(f"Server received event: {request}")
                if request.button_event.button_id == comms_pb2.ButtonEvent.ButtonId.BUTTON_2:
                    self.device_manager.handle_mode_event(request)
                elif request.button_event.button_id == comms_pb2.ButtonEvent.ButtonId.BUTTON_4:
                    self.device_manager.handle_play_event(request)
                elif request.button_event.button_id == comms_pb2.ButtonEvent.ButtonId.BUTTON_3:
                    self.device_manager.handle_stop_event(request)
                # respond with an ACK to keep the event loop going
                yield comms_pb2.DeviceEventResponse(ack=True)
        except grpc.RpcError as e:
            print(f"RPC error in EventStream: {e}")
        except Exception as e:
            print(f"Error in EventStream: {e}")

    def ServerAudioStream(self, request, context):
        '''
        Audio stream should have a logic block to look for the start message, 
        then yield to the data message until the end message is received.
        '''
        try:
            print(f"Server received audio stream request: {request}")
            
            while True:
                try:
                    # move this logic into  the EventStream function, put only message for audio transport into
                    # device_playback_queue
                    # yield to next(AudioStreamManager.opened())
                    # Check for Button 4 press event
                    event = device_playback_queue.get(timeout=1.0)  # 1 second timeout
                    if (hasattr(event, 'button_event') and 
                        event.button_event.button_id == comms_pb2.ButtonEvent.ButtonId.BUTTON_4):
                        # Send start packet
                        # does this yield work for the whole audio buffer? Do I have to chunk it in a helper function?
                        yield comms_pb2.AudioPacket(
                            is_start=True,
                            is_end=False,
                            data=b''
                        )
                        print("Server sent start packet")

                    if (hasattr(event, 'button_event') and 
                        event.button_event.button_id == comms_pb2.ButtonEvent.ButtonId.BUTTON_3):
                        # Send end packet
                        yield comms_pb2.AudioPacket(
                            is_start=False,
                            is_end=True,
                            data=b''
                        )
                        print("Server sent end packet")
                except queue.Empty:
                    # No events in queue, continue waiting
                    continue
                except grpc.RpcError as e:
                    print(f"RPC error in ServerAudioStream: {e}")
                    break
                except Exception as e:
                    print(f"Error in ServerAudioStream: {e}")
                    break

        except grpc.RpcError as e:
            print(f"RPC error in ServerAudioStream: {e}")
        except Exception as e:
            print(f"Error in ServerAudioStream: {e}")

def serve():
    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    comms_pb2_grpc.add_DeviceServiceServicer_to_server(DeviceServiceServicer(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig()
    serve()