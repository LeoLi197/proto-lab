import base64
import io
import wave
import unittest

from backend.features.ielts_study_system.router import _merge_audio_segments


class MergeAudioSegmentsTest(unittest.TestCase):
    def _make_wav(self, frames: bytes, *, channels: int = 1, sample_width: int = 2, frame_rate: int = 8000) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(frame_rate)
            wav_file.writeframes(frames)
        return buffer.getvalue()

    def test_merges_multiple_wav_segments_into_single_stream(self) -> None:
        frames_one = (b"\x01\x02" * 10)
        frames_two = (b"\x03\x04" * 5)
        wav_one = self._make_wav(frames_one)
        wav_two = self._make_wav(frames_two)

        segments = [
            (base64.b64encode(wav_one).decode("ascii"), "audio/wav", None),
            (base64.b64encode(wav_two).decode("ascii"), "audio/wav", None),
        ]

        merged_b64, mime = _merge_audio_segments(segments, "audio/wav")

        self.assertEqual(mime, "audio/wav")
        merged_bytes = base64.b64decode(merged_b64)
        with wave.open(io.BytesIO(merged_bytes), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getframerate(), 8000)
            self.assertEqual(wav_file.getnframes(), (len(frames_one) + len(frames_two)) // 2)
            merged_frames = wav_file.readframes(wav_file.getnframes())
        self.assertEqual(merged_frames, frames_one + frames_two)


if __name__ == "__main__":
    unittest.main()
