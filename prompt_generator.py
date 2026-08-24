"""Prompt generation helpers for short-form video production."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPack:
    """Generated prompts for a video scene."""

    photo_prompt: str
    animation_prompt: str
    negative_prompt: str


def generate_prompt_pack(
    master_prompt: str,
    *,
    style: str,
    aspect_ratio: str,
    language: str,
    scenes: int,
) -> list[PromptPack]:
    """Create photo and image-to-video prompts from one master prompt."""
    base = master_prompt.strip()
    if not base:
        raise ValueError("Мастер-промпт пустой.")
    if scenes < 1:
        raise ValueError("Количество сцен должно быть больше нуля.")

    prompt_language = "Russian" if language == "Русский" else "English"
    packs: list[PromptPack] = []
    for scene_number in range(1, scenes + 1):
        photo_prompt = (
            f"Scene {scene_number}/{scenes}. Create a cinematic keyframe for: {base}. "
            f"Style: {style}. Aspect ratio: {aspect_ratio}. "
            "Strong composition, clear subject, production-ready lighting, no text overlays. "
            f"Write the final prompt in {prompt_language}."
        )
        animation_prompt = (
            f"Animate scene {scene_number}/{scenes} based on this keyframe: {base}. "
            "Use subtle camera motion, natural depth, smooth subject movement, stable anatomy, "
            "no flicker, no morphing, no sudden scene changes. "
            f"Style: {style}; aspect ratio: {aspect_ratio}; language: {prompt_language}."
        )
        negative_prompt = (
            "low quality, blurry, watermark, logo, unreadable text, extra fingers, "
            "deformed face, jitter, flicker, distorted objects, abrupt cuts"
        )
        packs.append(PromptPack(photo_prompt, animation_prompt, negative_prompt))
    return packs
