# Streaming Audio Server

## Generating protocol buffer code

`python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. comms.proto`
`python -m grpc_tools.protoc -I=. --python_out=. --pyi_out=. --grpc_python_out=.`

## Open Questions

* How will a synchronous implementation of the server work?
* How will an asynchronous implementation of the server work?
* What audio content will I use?
* How do I rebuild the protobuf files?
* How do I verify audio playback from the client works?
* How will the server handle concurrency for multiple device states?
* How does the device handle interrupts? (i.e. start a new audio file before the previous one is done playing)
* Cloud deploy? Weeeee, that's the easy part.