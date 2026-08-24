"""Streamlit interface for prompt generation, voiceover and video assembly."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from fish_voiceover import AUDIO_FORMATS, DEFAULT_MODEL, LATENCY_MODES, synthesize_to_file
from prompt_generator import generate_prompt_pack
from render_engine import assemble_video, write_srt

st.set_page_config(page_title="AI Video Studio", page_icon="🎬", layout="wide")
st.title("🎬 AI Video Studio")
st.caption("Промпты для фото/оживления, озвучка через Fish Audio API и монтаж ролика с субтитрами и музыкой.")

if "voiceover_path" not in st.session_state:
    st.session_state.voiceover_path = None
if "subtitle_text" not in st.session_state:
    st.session_state.subtitle_text = ""

prompt_tab, voice_tab, edit_tab = st.tabs(["1. Промпты", "2. Озвучка", "3. Монтаж"])

with prompt_tab:
    st.subheader("Генерация промптов по мастер-промпту")
    master_prompt = st.text_area(
        "Мастер-промпт",
        height=160,
        placeholder="Например: атмосферный ролик о запуске нового кофейного бренда в большом городе...",
    )
    left, middle, right = st.columns(3)
    with left:
        style = st.selectbox("Стиль", ["cinematic", "documentary", "commercial", "anime", "realistic", "fashion editorial"])
    with middle:
        aspect_ratio = st.selectbox("Формат", ["9:16", "16:9", "1:1", "4:5"])
    with right:
        scenes = st.number_input("Количество сцен", min_value=1, max_value=20, value=5)
    language = st.radio("Язык промптов", ["Русский", "English"], horizontal=True)

    if st.button("Сгенерировать промпты", type="primary"):
        try:
            packs = generate_prompt_pack(
                master_prompt,
                style=style,
                aspect_ratio=aspect_ratio,
                language=language,
                scenes=int(scenes),
            )
            combined = []
            for index, pack in enumerate(packs, start=1):
                st.markdown(f"### Сцена {index}")
                st.text_area("Промпт для фото", pack.photo_prompt, height=120, key=f"photo_{index}")
                st.text_area("Промпт для оживления", pack.animation_prompt, height=120, key=f"anim_{index}")
                st.text_area("Negative prompt", pack.negative_prompt, height=80, key=f"neg_{index}")
                combined.append(
                    f"## Сцена {index}\nФото: {pack.photo_prompt}\nВидео: {pack.animation_prompt}\nNegative: {pack.negative_prompt}"
                )
            st.download_button(
                "Скачать все промпты .txt",
                data="\n\n".join(combined),
                file_name="generated_prompts.txt",
            )
        except ValueError as error:
            st.error(str(error))

with voice_tab:
    st.subheader("Озвучка текста через Fish Audio")
    api_key = st.text_input("Fish Audio API key", value=os.getenv("FISH_API_KEY", ""), type="password")
    voice_text = st.text_area("Текст озвучки", height=220, placeholder="Вставьте сценарий ролика...")
    col1, col2, col3 = st.columns(3)
    with col1:
        reference_id = st.text_input("Reference ID голоса", placeholder="опционально")
    with col2:
        model = st.text_input("Модель", value=DEFAULT_MODEL)
    with col3:
        audio_format = st.selectbox("Формат аудио", AUDIO_FORMATS)
    col4, col5 = st.columns(2)
    with col4:
        latency = st.selectbox("Latency", ["Не указывать", *LATENCY_MODES])
    with col5:
        normalize_choice = st.selectbox("Normalize", ["Не указывать", "Да", "Нет"])

    if st.button("Сгенерировать озвучку", type="primary"):
        if not api_key:
            st.error("Введите Fish Audio API key или задайте FISH_API_KEY.")
        else:
            normalize = {"Да": True, "Нет": False}.get(normalize_choice)
            latency_value = None if latency == "Не указывать" else latency
            output = Path(tempfile.gettempdir()) / f"fish_voiceover.{audio_format}"
            try:
                synthesize_to_file(
                    voice_text,
                    output,
                    api_key=api_key,
                    model=model,
                    audio_format=audio_format,
                    reference_id=reference_id or None,
                    normalize=normalize,
                    latency=latency_value,
                )
                st.session_state.voiceover_path = str(output)
                st.session_state.subtitle_text = voice_text
                st.success(f"Озвучка готова: {output}")
                st.audio(output.read_bytes(), format=f"audio/{audio_format}")
                st.download_button("Скачать озвучку", data=output.read_bytes(), file_name=output.name)
            except (RuntimeError, ValueError) as error:
                st.error(str(error))

with edit_tab:
    st.subheader("Монтаж: медиа + озвучка + субтитры + музыка")
    st.info("Для сборки нужен установленный FFmpeg. Загрузите фото/видео, добавьте озвучку и при необходимости музыку.")
    media_files = st.file_uploader(
        "Фото или видео для ролика",
        accept_multiple_files=True,
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "mkv", "webm"],
    )
    uploaded_voice = st.file_uploader("Озвучка, если не генерировали во вкладке 2", type=["mp3", "wav", "m4a", "aac"])
    music_file = st.file_uploader("Фоновая музыка", type=["mp3", "wav", "m4a", "aac"])
    subtitle_text = st.text_area(
        "Текст субтитров",
        value=st.session_state.subtitle_text,
        height=160,
        help="Если оставить пустым, субтитры не будут наложены.",
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        seconds_per_image = st.number_input("Секунд на фото", min_value=1.0, max_value=20.0, value=4.0, step=0.5)
    with col2:
        resolution = st.selectbox("Разрешение", ["1080x1920", "1920x1080", "1080x1080"])
    with col3:
        music_volume = st.slider("Громкость музыки", 0.0, 1.0, 0.18, 0.01)

    if st.button("Собрать ролик", type="primary"):
        try:
            width, height = [int(part) for part in resolution.split("x")]
            with tempfile.TemporaryDirectory() as temp_dir:
                workdir = Path(temp_dir)
                media_paths = []
                for index, uploaded in enumerate(media_files or [], start=1):
                    media_path = workdir / f"media_{index}_{uploaded.name}"
                    media_path.write_bytes(uploaded.getbuffer())
                    media_paths.append(media_path)

                if uploaded_voice:
                    voice_path = workdir / uploaded_voice.name
                    voice_path.write_bytes(uploaded_voice.getbuffer())
                elif st.session_state.voiceover_path:
                    voice_path = Path(st.session_state.voiceover_path)
                else:
                    raise ValueError("Добавьте или сгенерируйте озвучку.")

                music_path = None
                if music_file:
                    music_path = workdir / music_file.name
                    music_path.write_bytes(music_file.getbuffer())

                subtitles_path = None
                if subtitle_text.strip():
                    duration = max(float(seconds_per_image) * max(len(media_paths), 1), 1.0)
                    subtitles_path = write_srt(subtitle_text, workdir / "subtitles.srt", duration)

                output_path = assemble_video(
                    media_paths,
                    voice_path,
                    workdir / "final_video.mp4",
                    subtitles_path=subtitles_path,
                    music_path=music_path,
                    width=width,
                    height=height,
                    seconds_per_image=float(seconds_per_image),
                    music_volume=float(music_volume),
                )
                result = output_path.read_bytes()
                st.success("Ролик собран.")
                st.video(result)
                st.download_button("Скачать MP4", data=result, file_name="final_video.mp4", mime="video/mp4")
        except (RuntimeError, ValueError) as error:
            st.error(str(error))
