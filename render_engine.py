"""FFmpeg-based video assembly helpers."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def require_ffmpeg() -> None:
    """Raise a clear error if ffmpeg is unavailable."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg не найден. Установите ffmpeg и повторите сборку ролика.")


def write_srt(text: str, output: Path, duration_seconds: float) -> Path:
    """Create a simple SRT file by splitting text into readable subtitle chunks."""
    words = text.split()
    if not words:
        output.write_text("", encoding="utf-8")
        return output

    chunks = textwrap.wrap(" ".join(words), width=52)
    chunk_duration = max(duration_seconds / max(len(chunks), 1), 1.0)
    lines: list[str] = []
    cursor = 0.0
    for index, chunk in enumerate(chunks, start=1):
        start = cursor
        end = min(duration_seconds, cursor + chunk_duration)
        lines.extend([str(index), f"{format_srt_time(start)} --> {format_srt_time(end)}", chunk, ""])
        cursor = end
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def format_srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def assemble_video(
    media_paths: list[Path],
    voiceover_path: Path,
    output_path: Path,
    *,
    subtitles_path: Path | None = None,
    music_path: Path | None = None,
    width: int = 1080,
    height: int = 1920,
    seconds_per_image: float = 4.0,
    music_volume: float = 0.18,
) -> Path:
    """Assemble uploaded media, voiceover, optional music and subtitles into one MP4."""
    require_ffmpeg()
    if not media_paths:
        raise ValueError("Добавьте хотя бы одно фото или видео для монтажа.")
    if not voiceover_path.exists():
        raise ValueError("Файл озвучки не найден.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    segments = [
        make_segment(path, output_path.parent, index, width, height, seconds_per_image)
        for index, path in enumerate(media_paths, start=1)
    ]
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )

    silent_video = output_path.parent / "silent_video.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent_video)])

    cmd = ["-i", str(silent_video), "-i", str(voiceover_path)]
    filter_parts: list[str] = []
    audio_map = "1:a"
    if music_path:
        cmd.extend(["-stream_loop", "-1", "-i", str(music_path)])
        filter_parts.append(f"[2:a]volume={music_volume}[music]")
        filter_parts.append("[1:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        audio_map = "[aout]"

    video_map = "0:v"
    if subtitles_path and subtitles_path.exists() and subtitles_path.read_text(encoding="utf-8").strip():
        escaped_subtitles = str(subtitles_path).replace("'", "'\\''")
        filter_parts.append(f"[0:v]subtitles='{escaped_subtitles}'[vout]")
        video_map = "[vout]"

    if filter_parts:
        cmd.extend(["-filter_complex", ";".join(filter_parts)])

    cmd.extend([
        "-map",
        video_map,
        "-map",
        audio_map,
        "-shortest",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ])
    run_ffmpeg(cmd)
    return output_path


def make_segment(
    source: Path,
    workdir: Path,
    index: int,
    width: int,
    height: int,
    seconds_per_image: float,
) -> Path:
    extension = source.suffix.lower()
    output = workdir / f"segment_{index:03}.mp4"
    scale_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )
    if extension in IMAGE_EXTENSIONS:
        run_ffmpeg([
            "-loop",
            "1",
            "-t",
            str(seconds_per_image),
            "-i",
            str(source),
            "-vf",
            scale_filter,
            "-r",
            "30",
            "-an",
            str(output),
        ])
    elif extension in VIDEO_EXTENSIONS:
        run_ffmpeg(["-i", str(source), "-vf", scale_filter, "-an", "-r", "30", str(output)])
    else:
        raise ValueError(f"Неподдерживаемый формат медиа: {source.name}")
    return output


def run_ffmpeg(arguments: list[str]) -> None:
    command = ["ffmpeg", "-y", *arguments]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "FFmpeg завершился с ошибкой.")
