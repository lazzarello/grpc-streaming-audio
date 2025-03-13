from concurrent import futures
import logging
import grpc
import comms_pb2
import comms_pb2_grpc
import queue
from device_manager import DeviceManager

# is this the right place to queue up messages? Might only need two, not three
device_state_queue = queue.Queue()
events_queue = queue.Queue()
device_playback_queue = queue.Queue()
devices_states = {}
sound_filename = 'playback.opus'
sound_buffer = open(sound_filename, 'rb')

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