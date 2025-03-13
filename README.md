# Streaming Audio Server

## See INSTRUCTIONS.md for the assignment description

## Generating protocol buffer code

`python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. comms.proto`

## Deployment

```bash
docker build -t streaming-audio-server .
docker run -p 50051:50051 streaming-audio-server
```

## Encoding Opus audio with Pipewire on Linux

```bash
sudo apt install opus-tools
pw-record --channels=1 --rate=48000 --format=s16 - | opusenc --raw --raw-rate 48000 --raw-chan 1 - playback.opus
```

## TODO

* Stream audio file from memory to AudioServerStream function. TODO: get better understanding of this aspect of gRPC.
* Audio transport control for single device
  * Complete audio transport control queue
* Device state control for multiple devices
  * Audio transport control for multiple devices
* Make an LED state transition flash-at-connect function, for fun!  
* turn off all LEDs on disconnect (this might be a client side thing)
* Fix bug where device set messages don't always send on button events.

## Open Questions

* How does the device handle interrupts? (i.e. start a new audio file before the previous one is done playing)
* Do I need to chunk the sound buffer from memory into multiple AudioPacket messages to play back streaming audio?
* How is an audio file closed? Does simply ending the stream from the server close it?

## Closed Questions

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
  A: Initially, a single python dictionary could work, especially with asyncio, might be different with threads.
* Cloud deploy? Weeeee, that's the easy part.
  A: Make a dockerfile and deploy to Render or something like that
