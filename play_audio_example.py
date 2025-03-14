import wave
import pyaudio

'''
this demonstrates that pyaudio is broken on Linux
'''
def play_audio_file(file_path="playback.wav"):
    # Set chunk size for streaming
    chunk_size = 1024
    
    # Open the WAV file
    wf = wave.open(file_path, "rb")
    
    # Create PyAudio instance
    pa = pyaudio.PyAudio()
    
    # Print audio file info
    print(f"Playing audio file: {file_path}")
    print(f"  Sample rate: {wf.getframerate()} Hz")
    print(f"  Channels: {wf.getnchannels()}")
    print(f"  Sample width: {wf.getsampwidth()} bytes")
    
    # Open audio stream with the WAV file's properties
    stream = pa.open(
        format=pa.get_format_from_width(wf.getsampwidth()),
        channels=wf.getnchannels(),
        rate=wf.getframerate(),
        output=True,
    )
    
    # Read the first chunk of audio data
    data = wf.readframes(chunk_size)
    
    # Play the file chunk by chunk
    while data:
        stream.write(data)
        data = wf.readframes(chunk_size)
    
    # Clean up resources
    stream.stop_stream()
    stream.close()
    pa.terminate()
    
    print("Playback finished")

if __name__ == "__main__":
    play_audio_file()