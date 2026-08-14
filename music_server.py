# music_server.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
import io, base64, json
from openai_chat import  AsyncOpenAI
from create_image_world import create_image
from music import music_generation, generate_song
from local_llm import release_local_model_async
import asyncio
import os
import re
import signal
import subprocess
import time
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()
PROJECT_DIR = Path(__file__).resolve().parent
app.mount('/static', StaticFiles(directory=PROJECT_DIR / 'static'), name='static')


class HistorySong(BaseModel):
    title: str
    lyrics: str
    audio_base64: str


class HistoryDownload(BaseModel):
    songs: list[HistorySong]

a_client =AsyncOpenAI(
    base_url=os.getenv("LLM_API_URL", "http://127.0.0.1:8080/v1"),
    api_key=os.getenv("LLM_API_KEY", "local-not-required"),
    )
sdxl_url = os.getenv("IMAGE_API_URL", "http://127.0.0.1:64656")

# genre_tags.json を読み込む
with (PROJECT_DIR / "genre_tags.json").open("r", encoding="utf-8") as f:
    genre_tags = json.load(f)

ACE_SERVER_PORT = 8085
ACE_SERVER_GPU = os.getenv("ACESTEP_CPP_GPU", "0")
ACE_SERVER_SCRIPT = Path(__file__).resolve().with_name("start_acestep_cpp.sh")
ACE_SERVER_LOG = Path(__file__).resolve().with_name("acestep_server.log")
ACE_MODELS = {
    "acestep-v15-turbo-Q4_K_M.gguf",
    "acestep-v15-turbo-Q8_0.gguf",
    "acestep-v15-xl-turbo-Q4_K_M.gguf",
}
_ace_server_config: tuple[str, str] | None = None
_ace_server_lock = asyncio.Lock()


def _ace_listener_pid() -> int | None:
    result = subprocess.run(
        ["ss", "-ltnp"], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        if f":{ACE_SERVER_PORT} " not in line:
            continue
        match = re.search(r'pid=(\d+)', line)
        if not match:
            continue
        pid = int(match.group(1))
        try:
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except (FileNotFoundError, PermissionError):
            continue
        if "ace-server" not in command:
            raise RuntimeError(f"Port {ACE_SERVER_PORT} is occupied by a non-ACE process")
        return pid
    return None


def _restart_ace_server(model: str, memory_mode: str) -> None:
    pid = _ace_listener_pid()
    if pid is not None:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and _ace_listener_pid() is not None:
            time.sleep(.1)
        if _ace_listener_pid() is not None:
            raise RuntimeError("ACE-Step server did not stop within 15 seconds")

    command = [str(ACE_SERVER_SCRIPT), "--backend", "cuda", "--gpu", ACE_SERVER_GPU]
    if memory_mode == "keep_loaded":
        command.append("--keep-loaded")
    environment = os.environ.copy()
    environment["ACESTEP_CPP_SYNTH_MODEL"] = model
    log = ACE_SERVER_LOG.open("ab", buffering=0)
    try:
        subprocess.Popen(
            command,
            cwd=ACE_SERVER_SCRIPT.parent,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if _ace_listener_pid() is not None:
            return
        time.sleep(.2)
    raise RuntimeError("ACE-Step server did not start within 30 seconds")


def _stop_ace_server() -> None:
    pid = _ace_listener_pid()
    if pid is None:
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and _ace_listener_pid() is not None:
        time.sleep(.1)
    if _ace_listener_pid() is not None:
        raise RuntimeError("ACE-Step server did not stop within 15 seconds")


async def release_ace_for_local_llm() -> None:
    """Free keep-loaded ACE modules before loading the local Gemma model."""
    global _ace_server_config
    async with _ace_server_lock:
        await asyncio.to_thread(_stop_ace_server)
        _ace_server_config = None


async def ensure_ace_server(model: str, memory_mode: str) -> None:
    global _ace_server_config
    if model not in ACE_MODELS:
        raise ValueError(f"Unsupported local ACE-Step model: {model}")
    if memory_mode not in {"keep_loaded", "strict"}:
        raise ValueError(f"Unsupported ACE-Step VRAM mode: {memory_mode}")
    requested = (model, memory_mode)
    async with _ace_server_lock:
        if _ace_server_config == requested and _ace_listener_pid() is not None:
            return
        await asyncio.to_thread(_restart_ace_server, model, memory_mode)
        _ace_server_config = requested

@app.get('/')
async def read_index():
    return FileResponse(PROJECT_DIR / 'templates' / 'index.html')


def _safe_song_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', title).strip().strip('.')
    return name[:120] or '無題'


@app.post('/download_history_zip')
async def download_history_zip(payload: HistoryDownload):
    if not payload.songs:
        return JSONResponse({'err': '生成済みの曲がありません'}, status_code=400)
    archive = io.BytesIO()
    used_names: dict[str, int] = {}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for song in payload.songs:
            base_name = _safe_song_filename(song.title)
            used_names[base_name] = used_names.get(base_name, 0) + 1
            suffix = '' if used_names[base_name] == 1 else f'_{used_names[base_name]}'
            filename = f'{base_name}{suffix}'
            try:
                encoded = song.audio_base64.split(',', 1)[-1]
                audio = base64.b64decode(encoded, validate=True)
            except (ValueError, base64.binascii.Error):
                return JSONResponse(
                    {'err': f'{song.title}の音声データが不正です'}, status_code=400
                )
            output.writestr(f'{filename}.mp3', audio)
            output.writestr(f'{filename}.txt', song.lyrics.encode('utf-8'))
    archive.seek(0)
    return StreamingResponse(
        archive,
        media_type='application/zip',
        headers={'Content-Disposition': "attachment; filename*=UTF-8''%E7%94%9F%E6%88%90%E3%81%97%E3%81%9F%E6%9B%B2.zip"},
    )

@app.post('/generate_lyrics')
async def generate(
    request: Request,
    user_input: str = Form(""),
    previouse_title: str = Form(""),
    no_vocal: bool = Form(False),
    music_backend: str = Form("local_cpp"),
    vocal_language: str = Form("ja"),
    thinking: bool = Form(True),
    audio_duration: int = Form(-1),
    lyrics_format: str = Form("ace15"),
):
    if user_input is None or user_input.strip() == "":
        user_input = "おまかせで音楽を生成してください"

    # ボーカルなしの場合は、プロンプトにinstrumentalを追加
    if no_vocal:
        user_input = f"instrumental music, no vocal, {user_input}"
        print(f"ボーカルなしモード: プロンプトを'{user_input}'に変更しました")

    try:
        if music_backend == "local_cpp":
            # 2曲目以降はACEの常駐モデルを先に解放してGemma用VRAMを確保する。
            await release_ace_for_local_llm()
        success, lyrics_dict, music_world, _ = await music_generation(
            user_input, genre_tags, previouse_title, music_backend,
            vocal_language, thinking, audio_duration, no_vocal, lyrics_format,
        )
    except Exception as error:
        print(f"作詞処理中の予期しないエラー: {error}")
        return JSONResponse(
            {'err': f'LLMでの作詞に失敗しました: {error}'},
            status_code=502,
        )
    finally:
        if music_backend == "local_cpp":
            # 次の作曲工程へGPUを完全に明け渡す。
            await release_local_model_async()
    if not success:
        return JSONResponse(
            {'err': 'LLMが有効な歌詞データを返しませんでした'},
            status_code=502,
        )
    print("music_world=",music_world)
    print("lyrics_dict=",lyrics_dict)
    result=True
    return JSONResponse({"result":result,"lyrics_dict": lyrics_dict, "music_world":music_world})

@app.post('/generate_music')
async def generate_music(request: Request,
                         lyrics_dict: str = Form(...),
                         infer_step: int = Form(27),
                         guidance_scale: float = Form(3),
                         music_world: str = Form(...),
                         height: int = Form(976),
                         width: int = Form(1296),
                         no_vocal: bool = Form(False),
                         audio_duration: int = Form(-1),
                         ace_model: str = Form("acestep-v15-turbo-Q4_K_M.gguf"),
                         ace_memory_mode: str = Form("keep_loaded"),
                         vocal_language: str = Form("ja"),
                         thinking: bool = Form(True),
                         bpm: str = Form(""),
                         key_scale: str = Form(""),
                         seed: str = Form(""),
                         music_backend: str = Form("local_cpp")):
    music_world = json.loads(music_world.replace(" ", ""))
    print("music_world=",music_world)
    lyrics_dict = json.loads(lyrics_dict.replace(" ", ""))
    print("lyrics_dict=",lyrics_dict)
    print(f"no_vocal parameter received: {no_vocal}")
    print(f"audio_duration parameter received: {audio_duration}")
    # ① 音楽生成の結果を取得
    #generate_song から bytes が返ってくる想定
    # 並列処理で音楽と画像を生成
    try:
        if music_backend == "local_cpp":
            await release_local_model_async()
            await ensure_ace_server(ace_model, ace_memory_mode)
        audio_task = asyncio.to_thread(
            generate_song, lyrics_dict, infer_step, guidance_scale, no_vocal,
            audio_duration, ace_model, vocal_language, thinking,
            int(bpm) if bpm else None, key_scale or None, int(seed) if seed else None,
            music_backend,
        )
        if music_backend == "local_cpp":
            audio_bytes = await audio_task
            pil_image = None
        else:
            image_task = create_image(sdxl_url, a_client, music_world, "text2image", "t2i",height,width)
            audio_bytes, pil_image = await asyncio.gather(audio_task, image_task)

        # 画像生成に失敗した場合のフォールバック処理
        if pil_image is None and music_backend != "local_cpp":
            # デフォルト画像を作成またはプレースホルダー画像を使用
            from PIL import Image, ImageDraw, ImageFont
            pil_image = Image.new('RGB', (width, height), color=(100, 150, 200))
            draw = ImageDraw.Draw(pil_image)

            # フォントサイズを動的に調整
            font_size = min(width, height) // 20
            try:
                # デフォルトフォントを使用
                font = ImageFont.load_default()
            except:
                font = None

            text = "♪ Generated Music ♪"
            # テキストを中央に配置
            if font:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                text_width = len(text) * 10  # 大まかな推定
                text_height = 20

            x = (width - text_width) // 2
            y = (height - text_height) // 2
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
            print("デフォルト画像を生成しました")

        image_base64 = None
        if pil_image is not None:
            buf = io.BytesIO()
            pil_image.save(buf, format='PNG')
            image_base64 = 'data:image/png;base64,' + __import__('base64').b64encode(buf.getvalue()).decode()

    except Exception as e:
        print(f"音楽・画像生成中にエラーが発生しました: {e}")
        return JSONResponse({'err': f'音楽・画像生成に失敗しました: {str(e)}'}, status_code=500)
    # ④ 音声も Base64 にエンコード（Data URI スキーム）
    audio_base64 = 'data:audio/mp3;base64,' + base64.b64encode(audio_bytes).decode()
    # ⑤ JSON でまとめて返却
    print("generate_music_result:lyrics_dict =", lyrics_dict)
    return JSONResponse({
        'lyrics_json': json.dumps(lyrics_dict, ensure_ascii=False, indent=2),
        'image_base64': image_base64,
        'audio_base64': audio_base64,
    })

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'music_server:app',
        host=os.getenv('MOMO_HOST', '127.0.0.1'),
        port=int(os.getenv('MOMO_PORT', '64653')),
        reload=os.getenv('MOMO_RELOAD', '0') == '1',
    )
