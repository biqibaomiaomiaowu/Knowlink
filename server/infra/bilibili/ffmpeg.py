from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Callable, Protocol


class CancelToken(Protocol):
    canceled: bool


class MergeProcess(Protocol):
    def poll(self) -> int | None:
        ...

    def terminate(self) -> None:
        ...

    def kill(self) -> None:
        ...

    def wait(self, timeout: float | None = None) -> int | None:
        ...


class MergeCanceled(Exception):
    pass


class FfmpegMergeError(Exception):
    pass


class FfmpegMerger:
    def __init__(
        self,
        *,
        ffmpeg_path: str = "ffmpeg",
        run_command: Callable[[list[str]], int] | None = None,
        popen_factory: Callable[[list[str]], MergeProcess] | None = None,
        poll_interval_sec: float = 0.2,
        terminate_timeout_sec: float = 5,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.run_command = run_command
        self.popen_factory = popen_factory or self._popen
        self.poll_interval_sec = poll_interval_sec
        self.terminate_timeout_sec = terminate_timeout_sec

    def merge(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        *,
        cancel_token: CancelToken | None = None,
    ) -> Path:
        output = Path(output_path)
        if cancel_token is not None and cancel_token.canceled:
            output.unlink(missing_ok=True)
            raise MergeCanceled()
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c",
            "copy",
            str(output),
        ]
        try:
            if self.run_command is not None:
                exit_code = self.run_command(command)
            else:
                exit_code = self._run_process(command, cancel_token=cancel_token)
            if exit_code != 0:
                raise FfmpegMergeError(f"ffmpeg exited with status {exit_code}")
            return output
        except Exception:
            output.unlink(missing_ok=True)
            raise

    def _run_process(self, command: list[str], *, cancel_token: CancelToken | None) -> int:
        process = self.popen_factory(command)
        while True:
            return_code = process.poll()
            if return_code is not None:
                return return_code
            if cancel_token is not None and cancel_token.canceled:
                self._stop_process(process)
                raise MergeCanceled()
            time.sleep(self.poll_interval_sec)

    def _stop_process(self, process: MergeProcess) -> None:
        process.terminate()
        try:
            process.wait(timeout=self.terminate_timeout_sec)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=self.terminate_timeout_sec)

    @staticmethod
    def _popen(command: list[str]) -> MergeProcess:
        return subprocess.Popen(command)
