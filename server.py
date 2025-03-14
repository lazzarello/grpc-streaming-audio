from concurrent import futures
import logging
import grpc
import comms_pb2
import comms_pb2_grpc
from device_manager import DeviceManager
import audio

# TODO: save multiple device states in a dictionary
devices_states = {}
# this is the reference file for encoding settings, it is not played
# probably add a whole class later to do all the audio codec bits
sound_filename = 'playback.wav'
sound_buffer = audio.wave.open(sound_filename, 'rb')
samples_per_second = sound_buffer.getframerate()
# Print debugging information about the wave file
print(f"Wave file debugging information:")
print(f"  Sample rate: {samples_per_second} Hz")
print(f"  Channels: {sound_buffer.getnchannels()}")
print(f"  Sample width: {sound_buffer.getsampwidth()} bytes")
print(f"  Total frames: {sound_buffer.getnframes()}")
print(f"  Compression type: {sound_buffer.getcomptype()}")
print(f"  Duration: {sound_buffer.getnframes() / samples_per_second:.2f} seconds")
desired_frame_duration = 20/1000 # 20ms in seconds
desired_frame_size = int(desired_frame_duration * samples_per_second)
sound_buffer.close()

class DeviceServiceServicer(comms_pb2_grpc.DeviceServiceServicer):
    def __init__(self):
        self.device_manager = DeviceManager() # TODO: get id from metadata in client...
        self.opus_coder = audio.OpusCoder(sample_rate=48000, channels=1)

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
                event = self.device_manager.status_queue.get()
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
        Do we need an event queue here? IDK, seems like no but the good pattern is to have a queue.
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
        which opens the gRPC stream, then waits for a play event, then starts streaming audio.
        The transport controls are a bit of a mess, they might be redundantly using a second queue but hey, they work now...
        '''
        import queue
        
        try:
            print(f"Server received audio stream request: {request}")
            
            if request.start:
                print("Server received start packet")
                print("Waiting for play event...")
                
                # Main loop that watches for play events at 10Hz
                while True:
                    try:
                        # Poll the queue with a 0.1 second timeout (10Hz)
                        event = self.device_manager.audio_event_queue.get(block=True, timeout=0.1)
                        
                        if "play" in event:
                            if event["play"]:
                                # Play event received, start streaming audio
                                print("Play event received, starting audio stream")
                                sound_buffer = audio.wave.open(
                                    self.device_manager.audio_filenames[self.device_manager.mode], 'rb')
                                
                                # Send start packet with first chunk of audio
                                first_chunk = sound_buffer.readframes(desired_frame_size)
                                print(f"Server read first audio chunk {len(first_chunk)} long")
                                first_opus_data = self.opus_coder.encode(first_chunk)
                                yield comms_pb2.AudioPacket(
                                    is_start=True,
                                    is_end=False,
                                    data=bytes(first_opus_data)
                                )
                                print("Server sent start AudioPacket")

                                # Read and send all following audio data in chunks
                                streaming = True
                                while streaming:
                                    # Check for stop events while streaming
                                    try:
                                        stop_event = self.device_manager.audio_event_queue.get(block=False)
                                        if "play" in stop_event and not stop_event["play"]:
                                            print("Stop event received, stopping audio stream")
                                            streaming = False
                                            break
                                    except queue.Empty:
                                        # No stop event, continue streaming
                                        pass
                                    
                                    chunk = sound_buffer.readframes(desired_frame_size)
                                    if not chunk:
                                        break
                                    
                                    if len(chunk) // 2 == desired_frame_size:
                                        opus_data = self.opus_coder.encode(chunk)
                                        print(f"Server read audio chunk {len(chunk)} long")
                                        yield comms_pb2.AudioPacket(
                                            is_start=False,
                                            is_end=False,
                                            data=bytes(opus_data)
                                        )
                                    else:
                                        # Handle partial chunks
                                        # Convert to bytearray for easier manipulation
                                        # https://pyogg.readthedocs.io/en/latest/examples.html
                                        chunk_bytes = bytearray(chunk)
                                        # Calculate padding needed
                                        padding_needed = desired_frame_size - (len(chunk_bytes) // 2)
                                        # Add padding bytes (zeros)
                                        padded_data = chunk_bytes + b'\x00' * (padding_needed * 2)
                                        print(f"Server read padded audio chunk {len(chunk)} long and padded to {len(padded_data)}")
                                        opus_data = self.opus_coder.encode(padded_data)
                                        yield comms_pb2.AudioPacket(
                                            is_start=False,
                                            is_end=False,
                                            data=bytes(opus_data)
                                        )

                                # Send end packet
                                yield comms_pb2.AudioPacket(
                                    is_start=False,
                                    is_end=True,
                                    data=b''
                                )
                                print("Server sent end packet")
                                
                                # Close and reset sound buffer
                                sound_buffer.close()
                            else:
                                # Stop event received but not currently streaming
                                print("Server received Stop event received, but not currently streaming")
                    except queue.Empty:
                        # No event in queue, continue polling
                        continue
                
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