#!/usr/bin/env python3
"""Fish Audio Text-to-Speech helpers and CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_URL = "https://api.fish.audio/v1/tts"
DEFAULT_MODEL = "s2.1-pro"
DEFAULT_FORMAT = "mp3"
AUDIO_FORMATS = ("mp3", "wav", "pcm")
LATENCY_MODES = ("normal", "balanced")


def read_text(args: argparse.Namespace) -> str:
    """Read voiceover text from CLI arguments or stdin."""
    if args.text:
        return args.text.strip()
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    raise SystemExit("Передайте текст через --text, --text-file или stdin.")


def build_tts_payload(
    text: str,
    *,
    audio_format: str = DEFAULT_FORMAT,
    reference_id: str | None = None,
    normalize: bool | None = None,
    latency: str | None = None,
) -> dict[str, Any]:
    """Build a Fish Audio TTS request payload."""
    payload: dict[str, Any] = {
        "text": text,
        "format": audio_format,
    }
    if reference_id:
        payload["reference_id"] = reference_id
    if normalize is not None:
        payload["normalize"] = normalize
    if latency is not None:
        payload["latency"] = latency
    return payload


def build_payload(args: argparse.Namespace, text: str) -> dict[str, Any]:
    """Build a Fish Audio TTS payload from parsed CLI arguments."""
    return build_tts_payload(
        text,
        audio_format=args.format,
        reference_id=args.reference_id,
        normalize=args.normalize,
        latency=args.latency,
    )


def fish_tts(api_key: str, model: str, payload: dict[str, Any]) -> bytes:
    """Call Fish Audio TTS and return raw audio bytes."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": model,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fish Audio API вернул ошибку {error.code}: {details}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Не удалось подключиться к Fish Audio API: {error.reason}") from error


def synthesize_to_file(
    text: str,
    output: Path,
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    audio_format: str = DEFAULT_FORMAT,
    reference_id: str | None = None,
    normalize: bool | None = None,
    latency: str | None = None,
) -> Path:
    """Generate voiceover audio and save it to disk."""
    if not text.strip():
        raise ValueError("Текст для озвучки пустой.")
    payload = build_tts_payload(
        text.strip(),
        audio_format=audio_format,
        reference_id=reference_id,
        normalize=normalize,
        latency=latency,
    )
    audio = fish_tts(api_key=api_key, model=model, payload=payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(audio)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Создать аудио озвучку через Fish Audio API."
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text", help="Текст для озвучки.")
    input_group.add_argument("--text-file", help="UTF-8 файл со сценарием ролика.")
    parser.add_argument(
        "--output",
        "-o",
        default=f"voiceover.{DEFAULT_FORMAT}",
        help="Куда сохранить аудио файл (по умолчанию: voiceover.mp3).",
    )
    parser.add_argument(
        "--reference-id",
        help="ID голоса Fish Audio. Если не указан, используется голос по умолчанию API/модели.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Модель Fish Audio (по умолчанию: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--format",
        default=DEFAULT_FORMAT,
        choices=AUDIO_FORMATS,
        help=f"Формат аудио (по умолчанию: {DEFAULT_FORMAT}).",
    )
    parser.add_argument(
        "--latency",
        choices=LATENCY_MODES,
        help="Опциональный режим задержки, если доступен для выбранной модели.",
    )
    parser.add_argument(
        "--normalize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Включить или отключить нормализацию текста (--normalize / --no-normalize).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.getenv("FISH_API_KEY")
    if not api_key:
        raise SystemExit("Укажите API ключ в переменной окружения FISH_API_KEY.")

    try:
        output = synthesize_to_file(
            read_text(args),
            Path(args.output),
            api_key=api_key,
            model=args.model,
            audio_format=args.format,
            reference_id=args.reference_id,
            normalize=args.normalize,
            latency=args.latency,
        )
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error

    print(f"Готово: {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
