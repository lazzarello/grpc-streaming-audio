import os
import wave

import pyaudio


# this plays a file from disk, which is recording for each Play/Stop transition
# it could be a reference for how to stream the audio packets from the server
# pyaudio is broken on Linux, removed from the client.
def play_wav(file_path):
    chunk_size = 1024  # Read in chunks of 1024 samples
    wf = wave.open(file_path, "rb")

    pa = pyaudio.PyAudio()

    # Open a stream with the correct settings
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

    # Cleanup
    stream.stop_stream()
    stream.close()
    pa.terminate()


class OpusCoder:
    def __init__(self, sample_rate=48000, channels=1):
        if hasattr(os, "uname") and os.uname().sysname == "Darwin":
            os.environ["PYOGG_LIB_DIR"] = "/opt/homebrew/lib"  # for pyogg on macos
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = "/opt/homebrew/lib"  # for pyogg on macos

        import pyogg  # Lazy import to ensure env vars are set

        self.sample_rate = sample_rate
        self.channels = channels

        self.opus_encoder = pyogg.OpusEncoder()
        self.opus_encoder.set_application("audio")
        self.opus_encoder.set_sampling_frequency(sample_rate)
        self.opus_encoder.set_channels(channels)

        self.opus_decoder = pyogg.OpusDecoder()
        self.opus_decoder.set_sampling_frequency(sample_rate)
        self.opus_decoder.set_channels(channels)

    def encode(self, pcm_audio_bytes):
        # why is this 2048 bytes long when the chunk size is 1024?
        print(f"audio.py: Encoding audio chunk {len(pcm_audio_bytes)} long")
        return self.opus_encoder.encode(pcm_audio_bytes)

    def decode(self, opus_audio_bytes):
        return self.opus_decoder.decode(opus_audio_bytes)
