from concurrent import futures
import logging
import grpc
import comms_pb2
import comms_pb2_grpc

# implement functions outside of the proto class here. Helper functions.
def event_helper(event):
    pass

class DeviceServiceServicer(comms_pb2_grpc.DeviceServiceServicer):
    def StatusStream(self, request_iterator, context):
        '''
        Get the device status from the client, then loop over the request_iterator for status requests.
        '''
        return comms_pb2.DeviceStatusRequest(get=True)

    def EventStream(self, request_iterator, context):
        '''
        When the client and server have acknowledged the event, return an ack, then loop over the request_iterator for events.
        Write some event handler functions.
        '''
        return comms_pb2.DeviceEventResponse(ack=True)

    def ServerAudioStream(self, request, context):
        '''
        Audio stream should have a logic block to look for the start message, then yield to the data message until the end message is received.
        '''
        return super().ServerAudioStream(request, context)

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