from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

DEFAULT_VOICE = "es-ES-AlvaroNeural"


class TTSDependencyError(RuntimeError):
    pass


class TTSGenerationError(RuntimeError):
    pass


def html_to_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    text = raw_text
    if "<" in raw_text and ">" in raw_text:
        soup = BeautifulSoup(raw_text, "lxml")
        text = soup.get_text(" ", strip=True)

    return re.sub(r"\s+", " ", text).strip()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")


def build_cache_path(
    cache_dir: Path,
    date_str: str,
    section: str,
    voice: str,
    rate: float,
    output_format: str,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    normalized_rate = f"{rate:.2f}".rstrip("0").rstrip(".")
    filename = "_".join(
        [
            _slugify(date_str),
            _slugify(section),
            _slugify(voice),
            f"rate-{_slugify(normalized_rate)}",
        ]
    )
    return cache_dir / f"{filename}.{output_format}"


def _rate_to_edge_rate(rate: float) -> str:
    pct = round((rate - 1.0) * 100)
    return f"{pct:+d}%"


async def generate_tts_file(
    text: str,
    output_path: Path,
    voice: str,
    rate: float,
    output_format: str,
) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise TTSDependencyError("edge-tts is not installed") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rate_param = _rate_to_edge_rate(rate)

    if output_format == "mp3":
        tmp_output = output_path.with_suffix(".tmp.mp3")
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate_param,
        )
        await communicate.save(str(tmp_output))
        tmp_output.replace(output_path)
        return

    if output_format == "ogg":
        tmp_mp3 = output_path.with_suffix(".tmp.mp3")
        tmp_ogg = output_path.with_suffix(".tmp.ogg")

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate_param,
        )
        await communicate.save(str(tmp_mp3))

        try:
            process = await asyncio.to_thread(
                subprocess.run,
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(tmp_mp3),
                    "-c:a",
                    "libopus",
                    str(tmp_ogg),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            _ = process
        except FileNotFoundError as exc:
            raise TTSDependencyError("ffmpeg is required for ogg output") from exc
        except subprocess.CalledProcessError as exc:
            raise TTSGenerationError(f"ffmpeg conversion failed: {exc.stderr}") from exc
        finally:
            if tmp_mp3.exists():
                tmp_mp3.unlink()

        tmp_ogg.replace(output_path)
        return

    raise ValueError(f"Unsupported output format: {output_format}")
