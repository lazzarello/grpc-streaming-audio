# Streaming Audio Server

## See INSTRUCTIONS.md for the assignment description

## Generating protocol buffer code

`python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. comms.proto`

## Deployment in Docker

```bash
docker build -t device-server:local .
docker run -p 50051:50051 device-server:local
```

## Deployment in Kubernetes

microk8s is a single node kubernetes cluster. It can use images build locally if they are exported from docker and imported into the ctr cache. [Project documentation](https://microk8s.io/docs/registry-images)

```bash
snap install microk8s --classic
docker save device-server > device-server-export.tar
microk8s.ctr image import device-server-export.tar
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Encoding Opus audio with Pipewire on Linux

```bash
sudo apt install opus-tools
pw-record --channels=1 --rate=48000 --format=s16 - | opusenc --raw --raw-rate 48000 --raw-chan 1 - playback.opus
```

BUT, the encoder needs to be streaming, so read the file in as PCM wave data. See implementation in server.py

## TODO

* [Async implementation of state signalling](https://github.com/grpc/grpc/tree/master/examples/python/async_streaming) and audio stream example from gRPC source repo. This example uses threading and generators, [while another example](https://github.com/grpc/grpc/blob/master/examples/python/helloworld/async_greeter_server.py#L34) uses the newer `grpc.aio` module, which looks like it moves all the async bits into the server/client connection objects and keeps the other code looking similar enough, with async function definitions.
* Play streaming audio buffer on client with optional record option
* fix business logic in all streams to handle edge cases, especially re-connect
* change LED state where LED 1 illuminates when the server is connected
* Add encryption and authentication for client sessions

## Open Questions

## Closed Questions

* Why does the client queue up button events even when it's not connected to the server?
  A: because it's written that way...this should be changed for a production device
* How does the device handle interrupts? (i.e. start a new audio file before the previous one is done playing)
  A: it kind of does now but the timing and logic are not too good, if working at all. This can be improved with some more attention to the audio transport queue loop.
* Why is the reconnect logic not working as expected? As of 3/14/25 I have to toggle the stop button to get it into a state where it plays audio over the stream.
  A: because of a logic bug in the interaction between audio transport and the device state. On reconnect, the play button must be pressed once, it fails to play, then the stop button must be pressed once. From here the audio transport is in a state where it can play audio.
* Stop playback doesn't actually stop playback so maybe it isn't necessary?
  A: It is necessary since the mode cycles change which audio file is played
* What does the stop button do?
  A: In the comments of the client, it turns all LEDs off
* How do I use the finite state machine pattern for the device state + button events?
  A: From Termie "If play and stop do different things based on some other toggle etc you can start pretending that state machine is useful. But if they always play and always stop then that's just what they do"
* How is an audio file closed? Does simply ending the stream from the server close it?
  A: Yes, because it is read in chunks and exits when there are no more chunks
* Do I need to chunk the sound buffer from memory into multiple AudioPacket messages to play back streaming audio?
  A: Yes, see commit id 950cdd52ba78141a69786fa81d546f24018b2163
* Why is the client function handle_status_response actually using logic from requests, not responses? Without modifying the client, this is very confusing
  A: The terms "request" and "response" are very confusing in this test. I just figured that part out.
* Why doesn't the server ever enter the request_iterator loop when it gets a status request iterator?
  A: because the client needs a "primed response" which is the first yield in the StatusStream function.
* What does the Mode button do?
  A: Nothing, there is a handler for button 2 on the client but no mode logic on the server. Perhaps make it toggle some LEDs?
* How will a synchronous implementation of the server work?
  A: Using threads and queues, see server.py
* How will an asynchronous implementation of the server work?
  A: Using asyncio and async generators, see server_async.py
* What audio content will I use?
  A: A recording of my own voice! Encode it in Opus with the same settings in audio.py
* How do I rebuild the protobuf files?
  A: See README.md
* How will the server handle concurrency for multiple device states?
  A: Initially, a single python dictionary could work, especially with asyncio, might be different with threads. gRPC has [metadata available for each connection](https://grpc.io/docs/what-is-grpc/core-concepts/#bidirectional-streaming-rpc)
* Cloud deploy? Weeeee, that's the easy part.
  A: Make a dockerfile and deploy locally to microk8s, then deploy to a kubernetes service or just the docker imeage to Render or another cloud app platform.
