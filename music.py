import json
import asyncio
import re
from textwrap import dedent
from openai_chat import chat_req,AsyncOpenAI
from create_image_world import create_image
import requests
import time
import os
from urllib.parse import urljoin
from acestep_cpp_client import acestep_cpp_client
from local_llm import local_completion

# グローバル変数：ACE-Step-directAPIの初期化状態をキャッシュ
_ace_initialized = False
_last_check_time = 0
_check_interval = 300  # 5分間は初期化状態をキャッシュ

#---------------- OpenAI API -----------------
a_client =AsyncOpenAI(
    base_url=os.getenv("LLM_API_URL", "http://127.0.0.1:8080/v1"),
    api_key=os.getenv("LLM_API_KEY", "local-not-required"),
    )

sdxl_url = os.getenv("IMAGE_API_URL", "http://127.0.0.1:64656")

# ACE-Step 1.5 REST API（easy_music と同じタスクAPI）
ACE_API_BASE_URL = os.getenv("ACE_STEP_API_URL", "http://127.0.0.1:8001").rstrip("/")
ACE_RELEASE_ENDPOINT = f"{ACE_API_BASE_URL}/release_task"
ACE_QUERY_ENDPOINT = f"{ACE_API_BASE_URL}/query_result"
ACE_API_STATUS_ENDPOINT = f"{ACE_API_BASE_URL}/health"


async def llm(user_msg, music_backend="remote"):
    print("LLM")
    if music_backend == "local_cpp":
        return {"message": await local_completion(user_msg)}
    response_json = await chat_req(a_client, user_msg, "あなたは賢いAIです。userの要求や質問に正しく答えること")
    return {"message": response_json}


def _extract_json(text):
    """LLM返答からJSONオブジェクトを抽出する。"""
    if not text:
        raise ValueError("LLMの返答が空です")
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    candidate = fenced.group(1).strip() if fenced else text.strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        # 解説が前後に付いた場合は最初のJSONオブジェクを探す。
        start = candidate.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(candidate[start:])
    if not isinstance(value, dict):
        raise ValueError("LLMの返答がJSONオブジェクトではありません")
    return value


async def llm_json(prompt, music_backend="remote"):
    """JSONを要求し、壊れた返答はLLMに一度だけ修復させる。"""
    response = await llm(prompt, music_backend)
    text = response["message"]
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, ValueError) as error:
        print(f"JSONのパースに失敗。修復を試行します: {error}")
        repair_prompt = dedent(f"""
            以下の壊れたJSONを正しいJSONオブジェクトに修復してください。
            内容は変更せず、JSON以外の解説やMarkdownは出力しないでください。
            {text}
        """).strip()
        repaired = await llm(repair_prompt, music_backend)
        return _extract_json(repaired["message"])


def _normalize_lyrics_sections(value):
    """LLMの歌詞をGUI/ACE-Step共通のセクション辞書にする。"""
    if isinstance(value, dict):
        sections = {}
        for key, text in value.items():
            if text is None:
                continue
            if isinstance(text, list):
                sections[str(key)] = "\n".join(str(line).strip() for line in text if str(line).strip())
            else:
                sections[str(key)] = str(text)
        return sections
    if isinstance(value, list):
        sections = {}
        for item in value:
            nested = _normalize_lyrics_sections(item)
            sections.update(nested)
        return sections
    if not isinstance(value, str) or not value.strip():
        return {}

    text = value.strip()
    try:
        return _normalize_lyrics_sections(json.loads(text))
    except (json.JSONDecodeError, TypeError):
        pass

    # Gemmaが返すことのある `[[ "verse": "..." ]]` を救済する。
    if text.startswith("[[") and text.endswith("]]" ):
        try:
            return _normalize_lyrics_sections(json.loads("{" + text[2:-2].strip() + "}"))
        except json.JSONDecodeError:
            pass
    return {"verse": text}


def _lyrics_line_count(sections):
    return sum(
        1
        for text in sections.values()
        for line in str(text).splitlines()
        if line.strip()
    )


def _compact_genre_tags(genre_tags):
    """Keep the local prompt small while giving Gemma useful ACE-Step vocabulary."""
    limits = {"genre": 80, "instrument": 60, "mood": 50, "gender": 20, "timbre": 30}
    compact = {}
    for key, limit in limits.items():
        values = genre_tags.get(key, [])
        compact[key] = list(dict.fromkeys(str(value) for value in values))[:limit]
    return compact


def _parse_ace_lyrics(lyrics):
    """ACE-Step lyrics textを、表示用の順序付き辞書へ変換する。"""
    sections = {}
    current = None
    counts = {}
    for raw_line in str(lyrics or "").splitlines():
        line = raw_line.strip()
        match = re.fullmatch(r"\[([^\]]+)\]", line)
        if match:
            base = match.group(1).strip()
            counts[base] = counts.get(base, 0) + 1
            current = base if counts[base] == 1 else f"{base} {counts[base]}"
            sections[current] = ""
        elif current and line:
            sections[current] += ("\n" if sections[current] else "") + line
    return sections


def _ace_vocal_line_count(lyrics):
    instrumental = {"intro", "outro", "instrumental", "inst"}
    return sum(
        len([line for line in text.splitlines() if line.strip()])
        for name, text in _parse_ace_lyrics(lyrics).items()
        if re.sub(r"\s+\d+$", "", name).lower() not in instrumental
    )


async def _local_e4b_music_generation(
    user_input, genre_tags, previouse_title, vocal_language="ja",
    thinking=True, audio_duration=-1, no_vocal=False,
):
    """Gemma 4 E4BからACE-Step 1.5の正式な歌詞・caption形式を作る。"""
    language_names = {"ja": "日本語", "en": "英語", "zh": "中国語", "ko": "韓国語"}
    language = language_names.get(vocal_language, "日本語")
    duration = int(audio_duration) if int(audio_duration) > 0 else 120
    target_lines = 10 if duration < 60 else 16 if duration < 90 else 24
    caption_rule = (
        "30～60語の自然な英語1文。ジャンル/時代、ムード、ボーカル特性を含め、楽器名の列挙は禁止"
        if thinking else
        "3～5文の詳細な英語プロダクション指示。ジャンル、ムード、ボーカル、展開、音響を自然な文章で記述"
    )
    song_prompt = dedent(f"""
        あなたは作詞家であり、ACE-Step 1.5用の音楽ディレクターです。
        ユーザーの依頼から一曲分のデータを作成し、JSONオブジェクトだけを返してください。
        Markdown、コードフェンス、前置き、説明文は禁止です。

        必須JSON構造:
        {{
          "title": "曲名",
          "lyrics": "[Intro]\\n\\n[Verse]\\n歌詞...\\n\\n[Chorus]\\n歌詞...\\n\\n[Outro]",
          "caption": "ACE-Step 1.5向けの自然な英語説明",
          "theme": "日本語の主題",
          "atmosphere": "日本語の雰囲気"
        }}

        作詞規則:
        - 歌詞は{language}のみ。翻訳、ローマ字併記、説明文は禁止。
        - 歌唱部は[Verse]、[Pre-Chorus]、[Chorus]、[Bridge]を使う。
        - [Intro]、[Outro]、[Instrumental]、ソロ系タグの直下には歌詞を書かない。
        - {duration}秒の曲として約{target_lines}行以上を目安に、複数のVerseと反復Chorusで一曲分の展開を作る。
        - 指定された歌詞は文言を変えず、ACE-Stepのセクションへ配置する。
        - captionは{caption_rule}。
        - captionで角括弧タグや単なるカンマ区切りキーワード列を使わない。
        - インストゥルメンタル指定時はlyricsを"[Instrumental]"だけにし、歌詞を書かない。

        前回のタイトル: {previouse_title or "なし"}
        ボーカルなし: {"はい" if no_vocal else "いいえ"}
        ユーザーの依頼: {user_input}
    """).strip()

    song = await llm_json(song_prompt, "local_cpp")
    ace_lyrics = str(song.get("lyrics", "")).strip()
    valid = no_vocal or (
        "[Verse" in ace_lyrics and "[Chorus" in ace_lyrics
        and _ace_vocal_line_count(ace_lyrics) >= max(8, target_lines - 4)
    )
    if not valid:
        correction_prompt = dedent(f"""
            次のJSONのlyricsだけをACE-Step 1.5形式へ修正し、JSONだけを返してください。
            [Verse]と[Chorus]を含め、{language}だけで{target_lines}行以上にしてください。
            [Intro]と[Outro]の直下には歌詞を書かないでください。caption等は維持してください。
            JSON: {json.dumps(song, ensure_ascii=False)}
        """).strip()
        song = await llm_json(correction_prompt, "local_cpp")
        ace_lyrics = str(song.get("lyrics", "")).strip()
    if not no_vocal and ("[Verse" not in ace_lyrics or "[Chorus" not in ace_lyrics):
        raise ValueError("Gemma 4 E4BがACE-Step 1.5の歌詞構造を返しませんでした")

    song["ace_lyrics"] = "[Instrumental]" if no_vocal else ace_lyrics
    song["lyrics"] = ({"Instrumental": ""} if no_vocal else _parse_ace_lyrics(ace_lyrics))
    song["genre"] = str(song.get("caption") or song.get("genre") or "").strip()

    description_prompt = dedent(f"""
        次の曲について、音楽の解説を日本語で120文字から220文字にまとめてください。
        ジャンル、楽器、曲調、歌詞の意図に触れてください。
        タイトルや歌詞本文を繰り返さず、Markdown記号、見出し、JSON、完成したという表現は使わないでください。
        曲データ: {json.dumps(song, ensure_ascii=False)}
    """).strip()
    description = await llm(description_prompt, "local_cpp")
    return True, song, description, ""


async def music_generation(
    user_input, genre_tags, previouse_title, music_backend="remote",
    vocal_language="ja", thinking=True, audio_duration=-1, no_vocal=False,
):
    print("=====>>>>>user_input=",user_input)
    if music_backend == "local_cpp":
        return await _local_e4b_music_generation(
            user_input, genre_tags, previouse_title, vocal_language,
            thinking, audio_duration, no_vocal,
        )
    request_song = dedent(f"""
        ユーザーの入力の意図を正確に判断して選択肢から選び、指定されたワードを返しなさい。選択肢->
        1) autoや、おまかせの場合の指定ワードは'generatSong',
        2) 歌詞を指定している場合の指定ワードは'lyrics',
        3) 曲のジャンルやテーマを入力している場合の指定ワードは'genre',
        4) 歌詞の雰囲気を入力していると判断できる場合の指定ワードは'theme',
        5) 曲のタイトルを入力していると判断できる場合の指定ワードは'title',
        検出された指定ワードは、json内に記載すること。
        user_inputにタイトル、ジャンル、ムード、楽器について記載がある場合は、各々をjesonのtitle、genre、atmosphereにinstruments記載すること。
        json形式は以下の通りとする。必ずすべてのキーを記載すること。必ずjson形式で出力すること。
        楽器が記載されている場合は、genreに追加すること。
        ただし、json形式の出力は以下のようにコードブロックで囲むこと。
        ```json
        {{"word": "指定ワード", "title": "タイトル", "lyrics": "歌詞", "genre": "ジャンル", "theme": "テーマ", "atmosphere": "歌詞の雰囲気", "instruments": "楽器"}}
        ```
        該当がない場合の指定ワードはnullです。「これで良いか聞いてください」のような確認文は使ってはいけません。
        ユーザーの入力={user_input}
    """).strip()
    print("request_song=", request_song)
    try:
        json_data = await llm_json(request_song, music_backend)
        print("抽出されたJSONデータ:", json_data)
    except (json.JSONDecodeError, ValueError) as error:
        print("JSONの修復にも失敗しました:", error)
        return await gen_lyrics(None, None, None, user_input, None, None, genre_tags, music_backend)
    sel_word = json_data.get('word', None)
    print("sel_word=", sel_word)

    # sel_wordから処理を分岐
    if sel_word == "generatSong":
        song_generate = "音楽の生成をする場合のタイトルを一つだけ提案してください。\
            タイトルは様々な場面や時間、景色、思い、人、モノ、世界など、音楽のタイトルに相応しいことを想定して多彩で変化に富む内容を考えること。\
            例えは、故郷、夕暮れ、星、思い出、愛、旅、夢、静か、夜、都会、山、海、アニメ、ロボット、AI、未来、過去、世界、日本、大阪、東京、その他の都市、など、\
            これ以外も考慮しつつ多彩なテーマからタイトルを選ぶ。音楽のジャンルや雰囲気をから考えるのも効果的です。\
            LLMの持つ特性に偏りがちなので自らの特性にこだわらないタイトルを考えること。タイトルは必ず記入すること。内容だけで説明は不要です。\
            タイトルは日本で作成して下さい。難しい漢字は使わないこと。前回とは異なる雰囲気やテーマのタイトルを考えてください。前回作成したタイトルは以下の通りです。前回作のタイトル="
        song_generate =song_generate+ previouse_title
        response = await llm(song_generate, music_backend)
        print("おまかせesponse=", response)
        return await music_generation(response["message"], genre_tags, previouse_title, music_backend)
    elif sel_word in ["lyrics", "genre", "theme", "atmosphere",'title']:
        return await gen_lyrics(
            json_data.get('title'), json_data.get('lyrics'), json_data.get('genre'),
            json_data.get('theme'), json_data.get('atmosphere'),
            json_data.get('instruments'), genre_tags, music_backend,
        )
    else:
        print("意図分類が不明なため、入力全体をテーマとして作詞します")
        return await gen_lyrics(None, None, None, user_input, None, None, genre_tags, music_backend)


#　歌詞、ジャンル、テーマ,雰囲気　から作詞と作曲をする
async def gen_lyrics(title, lyrics, genre, theme, atmosphere, instruments, genre_tags, music_backend="remote"):
    json_data = {
        "title":title,
        "lyrics": lyrics,
        "genre": genre,
        "theme": theme,
        "atmosphere": atmosphere,
        "instruments":instruments,
    }
    request_msg = dedent(f"""
        jsonDataで示されたユーザーの作曲の意図を正確に判断して作詞のための指定されたlyrics形式と作曲のためのgenreを作成しなさい。
        title、歌詞、ジャンル、ムード（雰囲気）、楽器はユーザー入力に記載があればそのまま採用すること。
        ただし、ジャンル、ムード（雰囲気）、楽器は日本語で入力された場合はそのまま採用せず、必ず英語に翻訳すること。
         "genre"については、ユーザーの入力を採用しても、追加で曲の雰囲気にある、他のタグを追加しても構いません。
        lyrics形式を作成するきには、ユーザーのリクエストの"lyrics"に歌詞ががあればそのまま変形せずに歌詞として使ってlyrics形式を作成すること。
        ユーザーのリクエストの"lyrics"がすでにlyrics形式の場合はそのまま採用すること。
        ユーザーのリクエストの"lyrics"に歌詞がない場合のlyrics形式は、歌詞の内容を表すものとして、曲のジャンルやテーマ、歌詞の雰囲気を考慮して作成すること。
        英語の歌詞は書いてはいけません。英単語も使ってはいけません。更に日本語以外、他のどのような言語も使わないこと。
        ユーザーのクエストに長さ指定のような記載があれば従ってください、無ければ15行前後の歌詞を作成すること。30行よりも長い歌詞は作成しないこと。
        lyricsの形式の見本は以下のとおりです。ただし、詞や曲の内容に応じて、"verse"、"chorus", "bridge", "outro"を作曲の理論を参照しつつ、組み合わせること。
        "verse"、"chorus", "bridge"は複数回使っても構いません。形式は必ず"verse"、"chorus", "bridge", "outro"を1回以上使う恋と。
        "verse1","verse2"のように複数回使うことも可能です。曲の雰囲気に合わせて、慎重に考えてください。歌詞の形式は必ず以下の見本のように[[ }}形式にすること。
        歌詞の形式の基本的な見本={{"verse": "歌詞の内容", "chorus": "歌詞の内容", "bridge": "歌詞の内容", "outro": "歌詞の内容"}}
        genreの作成は以下のタグが定義されたjsonを参考にしてください。
        'genre'、'instrument'、'mood'、'gender'、'timbre'の各キーから必要に応じて一つ以上のタグを採用してください。
        genre作成用json={json.dumps(genre_tags, ensure_ascii=False)}
        作成したlyrics形式は、以下のjson形式のlyricsの要素に記載すること。各要素は必ず記入すること。出力のjson形式は以下の通りです。
        {{"title": "タイトル", "lyrics": {{"verse": "歌詞", "chorus": "歌詞", "bridge": "歌詞", "outro": "歌詞"}}, "genre": "ジャンル", "theme": "テーマ", "atmosphere": "雰囲気"}}
        lyricsの値は必ずJSONオブジェクトとし、文字列や配列にしないこと。
        verse、chorus、bridge、outroの各値には、改行で区切った4行から5行の歌詞を必ず記載すること。
        各行は短い単語だけで終わらせず、情景や感情が伝わる意味の通った一文にすること。
        JSON文字列内の改行は必ず\\nとして表現し、歌詞全体を合計16行以上20行以下にすること。
        1セクションを1行だけで終わらせてはいけません。
        解説は不要です。参考にするユーザーのリクエストは以下のjson形式で示します。
        jsonData={json.dumps(json_data, ensure_ascii=False)}
    """).strip()

    #print("request_msg=", request_msg)
    print("Setup prompt for generate lyrics & genere")
    try:
        json_data_m2 = await llm_json(request_msg, music_backend)
        json_data_m2["lyrics"] = _normalize_lyrics_sections(json_data_m2.get("lyrics"))
        if not json_data_m2["lyrics"]:
            raise ValueError("歌詞セクションが空です")
        # 小型ローカルモデルがJSON例を優先して短く返した場合は、一度だけ書き直す。
        if music_backend == "local_cpp" and not lyrics and _lyrics_line_count(json_data_m2["lyrics"]) < 16:
            rewrite_prompt = dedent(f"""
                次の歌詞JSONは短すぎます。タイトル、ジャンル、テーマ、雰囲気は維持して、
                lyricsだけを充実させた完全なJSONオブジェクトを書き直してください。
                verse、chorus、bridge、outroを必ず含め、各セクションは改行で区切った
                4行から5行、全体で16行以上20行以下にしてください。
                各行は短い語句ではなく、情景や感情が伝わる意味の通った一文にしてください。
                JSON文字列内の改行は\\nで表現してください。Markdownや説明は禁止です。
                元のJSON={json.dumps(json_data_m2, ensure_ascii=False)}
            """).strip()
            json_data_m2 = await llm_json(rewrite_prompt, music_backend)
            json_data_m2["lyrics"] = _normalize_lyrics_sections(json_data_m2.get("lyrics"))
            if _lyrics_line_count(json_data_m2["lyrics"]) < 16:
                raise ValueError("ローカルLLMの歌詞が16行未満です")
        print("Extracted JSON object jsonData_m2:", json_data_m2)
        result = True
    except (json.JSONDecodeError, ValueError) as error:
        print("JSONの修復にも失敗しました:", error)
        result = False

    if result:
        end_detail = dedent(f"""
            作曲ができたので、歌詞部分だけを抜き出して表示してください。
            ただし、verse、chorus、bridge、outroの各単語は文章には入れないでください。
            歌詞の表示は、改行で区切って出力すること。その後に曲の説明と意図を簡単に説明してください。
            曲の説明には曲が完成したことには触れないこと。
            曲のタイトルは'title'キーに、歌詞は'lyrics'キーに、曲のジャンルは'genre'キーにあります。
            その他の情報は'theme'、'atmosphere'のキーに記載されています。
            各々記載の内容は説明してもいいけど、キーやjsonの形式のデータは出力には入れないこと。
            コメントは、簡潔に説明すること。作曲の結果は次のjson形式で示します。
            作曲結果は以下の通りです。
            {json.dumps(json_data_m2, ensure_ascii=False)}
        """).strip()

        music_world = await llm(end_detail, music_backend)
        lyrics_m = "test"
        return result, json_data_m2, music_world, lyrics_m
    else:
        return result, None, None, None

def convert_lyrics_dict_to_text(lyrics_dict, no_vocal=False):
    """歌詞辞書をテキストに変換する関数

    Args:
        lyrics_dict: 歌詞辞書
        no_vocal: True の場合、ACE-Step公式推奨のインストゥルメンタル形式（構造のみ）に変換

    Returns:
        str: 変換された歌詞テキスト
    """
    if not isinstance(lyrics_dict, dict):
        print(f"lyrics_dictは辞書型である必要があります。現在の型: {type(lyrics_dict)}")
        return lyrics_dict

    result = ""
    for key, value in lyrics_dict.items():
        if not isinstance(value, str):
            print(f"警告: 値が文字列ではありません。スキップします。キー: {key}, 値: {value}")
            continue

        processed_key = re.sub(r"[（(].*?[）)]", "", key).strip()

        if no_vocal:
            # ACE-Step公式推奨：歌詞の構造セクションのみを残す（テキストは削除）　　→　ボーカル削除では効果がなかった
            result += f"[{processed_key}]\n\n"
        else:
            # 通常モード：歌詞テキストも含める
            processed_value = re.sub(r"^[（(].*?[）)]\s*\n?", "", value)
            result += f"[{processed_key}]\n{processed_value}\n"

    return result.strip()

# 各キーの値をカンマ区切りで結合し、テキスト形式に変換
def convert_genre_to_text(genre_data):
    result = []
    for key, values in genre_data.items():
        # キーと値を結合してテキスト形式に変換
        result.append(f"{key}: {', '.join(values)}")
    return "\n".join(result)

# ++++++++++++++++++++++++　歌の生成　+++++++++++++++++++++++
def generate_song(
    jeson_song: dict, infer_step: int = 27, guidance_scale: float = 3,
    no_vocal: bool = False, audio_duration: int = -1,
    model: str = "acestep-v15-turbo-Q4_K_M.gguf", vocal_language: str = "ja",
    thinking: bool = True, bpm=None, key_scale=None, seed=None,
    music_backend: str = "remote",
):
    # JSON 文字列化
    print("======>>>>>jeson_song=",jeson_song)
    print(f"======>>>>>no_vocal parameter={no_vocal}")
    lyrics_dic = jeson_song['lyrics']
    print("###### lyrics_dic >>>>",lyrics_dic)
    lyrics = jeson_song.get('ace_lyrics') or convert_lyrics_dict_to_text(lyrics_dic, no_vocal)
    print("###### lyrics_text >>>>",lyrics)
    genre = jeson_song['genre']
    print("###### genre >>>>",genre)

    # ボーカルなしの場合：最も効果的な [inst] タグを使用
    if no_vocal:
        lyrics = "[inst]"  # 実際のテストで最も効果的だった方法
        print("=== 最も効果的なボーカル除去方法: [inst] タグ使用 ===")
        print(f"lyrics設定: '{lyrics}'")

        # ジャンルからボーカル関連キーワードを除去し、インストゥルメンタル指定を追加
        instrumental_prefix = "pure instrumental, no vocal, no voice, no singing, no human sound, no lyrics, no words, no speech, instrumental music only, background music, ambient music, instrumental track"

        vocal_keywords = [
            "vocal", "vocals", "singer", "voice", "singing", "song", "lyrics",
            "chorus", "verse", "rap", "chant", "human", "words", "speech",
            "vocal melody", "singer", "artist", "performer", "choir", "harmony",
            "lead vocal", "backing vocal", "vocal line", "sung", "choral"
        ]

        cleaned_genre = genre
        for keyword in vocal_keywords:
            # 大文字小文字両方をチェック
            cleaned_genre = cleaned_genre.replace(keyword, "").replace(keyword.capitalize(), "").replace(keyword.upper(), "")

        # 複数のスペースとカンマを整理
        cleaned_genre = " ".join(cleaned_genre.split()).replace(" ,", ",").replace(",,", ",").strip(",").strip()

        # 最終的なジャンル文字列（インストゥルメンタル指定を最優先）
        genre = f"{instrumental_prefix}, {cleaned_genre}" if cleaned_genre else instrumental_prefix

        print(f"=== 最も効果的なボーカル除去: [inst] タグアプローチ ===")
        print(f"歌詞設定: '{lyrics}'")
        print(f"強化されたインストゥルメンタル指定: '{genre}'")
        print("=" * 60)

    # APIに送信するデータの準備（ACE-Step-directAPI標準形式）
    data = {
        "audio_duration": audio_duration,  # フロントエンドから設定可能に変更
        "genre": genre,
        "infer_step": infer_step,
        "lyrics": lyrics,
        "guidance_scale": guidance_scale,
        "scheduler_type": "euler",
        "cfg_type": "apg",
        "guidance_interval": 0.5,
        "guidance_interval_decay": 0.0,
        "min_guidance_scale": 3,
        "use_erg_tag": True,
        "use_erg_lyric": False if no_vocal else True,  # ボーカルなしの場合は歌詞処理を完全無効化
        "use_erg_diffusion": True,
        "guidance_scale_text": 0.0,
        "guidance_scale_lyric": -1.0 if no_vocal else 0.0  # ボーカルなしの場合はより強力に抑制
    }

    # ボーカルなしの場合の追加強力設定
    if no_vocal:
        # ACE-Stepオリジナル準拠のボーカル抑制設定
        data.update({
            "guidance_scale_lyric": -3.0,     # 負の値でボーカルを強力に抑制（オリジナル準拠）
            "guidance_scale_text": 1.5,      # テキストガイダンスを少し強化
            "use_erg_lyric": False,           # 歌詞ERG処理を完全無効化
            "use_erg_diffusion": True,        # 拡散ERG処理は有効のまま
        })

        print("=== 最も効果的なインストゥルメンタル設定: [inst] タグ使用 ===")
        print(f"use_erg_lyric: {data['use_erg_lyric']}")
        print(f"use_erg_diffusion: {data['use_erg_diffusion']}")
        print(f"guidance_scale_lyric: {data['guidance_scale_lyric']}")
        print(f"guidance_scale_text: {data['guidance_scale_text']}")
        print(f"lyrics: '{lyrics}'")
        print(f"enhanced instrumental genre: '{genre}'")
        print("=" * 50)
    else:
        print("=== 通常のボーカル有り設定 ===")
        print(f"use_erg_lyric: {data['use_erg_lyric']}")
        print(f"guidance_scale_lyric: {data['guidance_scale_lyric']}")
        print("=" * 30)

    print(f"APIに送信するデータ: {data}")  # デバッグ用

    # ACE APIを呼び出し
    if music_backend == "local_cpp":
        return acestep_cpp_client.generate(
            caption=genre, lyrics=lyrics, duration=audio_duration,
            inference_steps=infer_step, guidance_scale=guidance_scale,
            vocal_language=vocal_language, bpm=bpm, keyscale=key_scale,
            seed=seed, instrumental=no_vocal, synth_model=model,
        )

    response = call_ace_api(data, no_vocal, model, vocal_language, thinking, bpm, key_scale, seed)

    if response is None:
        raise RuntimeError("ACE-Step 1.5での音楽生成に失敗しました")

    # サーバからのContent-Dispositionヘッダーからファイル名を抽出
    cd = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename="?([^"]+)"?', cd)
    filename = match.group(1) if match else "output.wav"

    # 音楽データをバイナリとして直接返す（music_server.pyとの互換性のため）
    print(f"音楽データを受信しました: {len(response.content)} bytes")
    return response.content

def check_ace_initialization():
    """ACE-Step-directAPIサーバーが既に初期化されているかチェック（キャッシュ付き）"""
    global _ace_initialized, _last_check_time

    current_time = time.time()

    # 最近チェックして初期化済みならスキップ
    if _ace_initialized and (current_time - _last_check_time) < _check_interval:
        print(f"✓ ACE-Step（キャッシュ済み）: 前回チェックから{int(current_time - _last_check_time)}秒")
        return True

    print("ACE-Step初期化状態を確認中...")

    # statusエンドポイントをチェック
    try:
        response = requests.get(ACE_API_STATUS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            try:
                json_resp = response.json()
                if json_resp.get('initialized', False):
                    print(f"✓ ACE-Step-directAPIは既に初期化済み: {ACE_API_STATUS_ENDPOINT}")
                    _ace_initialized = True
                    _last_check_time = current_time
                    return True
            except:
                pass
    except:
        pass

    # statusエンドポイントが無い場合、軽量なテストリクエストで確認
    # 軽量なテストデータ（最小パラメータ）
    test_data = {
        "format": "wav",
        "audio_duration": 3.0,  # 非常に短い
        "prompt": "test",
        "lyrics": "",
        "infer_step": 1,  # 最小ステップ
        "guidance_scale": 1.0,
        "scheduler_type": "euler",
        "cfg_type": "apg"
    }

    try:
        print(f"軽量テスト中: {ACE_API_ENDPOINT}")
        # 短いタイムアウトで確認
        response = requests.post(ACE_API_ENDPOINT, json=test_data, timeout=8)

        if response.status_code == 200:
            print(f"✓ ACE-Step-directAPIは初期化済み")
            _ace_initialized = True
            _last_check_time = current_time
            return True
        elif response.status_code == 500:
            # 500エラーは未初期化の可能性
            print(f"未初期化の可能性（500エラー）")
            _ace_initialized = False
            return False

    except requests.exceptions.Timeout:
        print(f"処理中の可能性（タイムアウト）")
        # タイムアウトは初期化済みと判断（処理中）
        _ace_initialized = True
        _last_check_time = current_time
        return True
    except Exception as e:
        print(f"チェックエラー: {str(e)}")

    _ace_initialized = False
    return False

def ensure_ace_initialization():
    """ACE-Step-directAPIサーバーの初期化を確実に実行（必要な場合のみ）"""
    global _ace_initialized, _last_check_time

    # まず初期化状態をチェック
    if check_ace_initialization():
        print("ACE-Step-directAPIは既に初期化済みです。スキップします。")
        return True

    print("ACE-Step-directAPIが未初期化のため、初期化を実行します...")

    try:
        print(f"ACE-Step-directAPI初期化を試行中: {ACE_API_INIT_ENDPOINT}")
        response = requests.post(ACE_API_INIT_ENDPOINT, json={}, timeout=90)  # タイムアウト延長

        if response.status_code == 200:
            try:
                json_resp = response.json()
                if json_resp.get('success', False):
                    print(f"✓ 初期化成功: {ACE_API_INIT_ENDPOINT}")
                    _ace_initialized = True
                    _last_check_time = time.time()
                    return True
                else:
                    print(f"初期化レスポンスでsuccess=False: {json_resp}")
            except:
                print(f"✓ 初期化完了（非JSONレスポンス）: {ACE_API_INIT_ENDPOINT}")
                _ace_initialized = True
                _last_check_time = time.time()
                return True
        else:
            print(f"✗ 初期化失敗 ({response.status_code}): {ACE_API_INIT_ENDPOINT}")
            print(f"Response: {response.text[:200]}")

    except requests.exceptions.RequestException as e:
        print(f"✗ 初期化接続エラー: {ACE_API_INIT_ENDPOINT} - {str(e)}")

    print("すべての初期化エンドポイントで失敗")
    _ace_initialized = False
    return False

def reset_ace_initialization_cache():
    """ACE-Step初期化キャッシュをリセット（テスト用）"""
    global _ace_initialized, _last_check_time
    _ace_initialized = False
    _last_check_time = 0
    print("ACE-Step初期化キャッシュをリセットしました")

def call_ace_api(
    data, no_vocal=False, model="acestep-v15-turbo", vocal_language="ja",
    thinking=True, bpm=None, key_scale=None, seed=None,
):
    """ACE-Step 1.5にタスクを投入し、完了後の音声レスポンスを返す。"""
    duration = data["audio_duration"]
    payload = {
        "prompt": data["genre"],
        "lyrics": data["lyrics"],
        "thinking": thinking,
        "model": model,
        "vocal_language": vocal_language,
        "audio_duration": duration if duration == -1 else max(10, min(300, duration)),
        "time_signature": "4",
        "batch_size": 1,
        "audio_format": "mp3",
        "inference_steps": max(1, min(200, data["infer_step"])),
        # 1.5のCFGは旧APIより小さい値が基準。GUIの範囲をAPI許容値に収める。
        "guidance_scale": max(0.0, min(20.0, data["guidance_scale"])),
        "instrumental": bool(no_vocal),
    }
    if bpm is not None:
        payload["bpm"] = bpm
    if key_scale:
        payload["key_scale"] = key_scale
    if seed is not None:
        payload["seed"] = seed
    print(f"ACE-Step 1.5 task request: {json.dumps(payload, ensure_ascii=False)}")

    try:
        release = requests.post(ACE_RELEASE_ENDPOINT, json=payload, timeout=60)
        release.raise_for_status()
        release_body = release.json()
        if release_body.get("code") != 200:
            raise RuntimeError(release_body.get("error") or "ACE-Step task creation failed")
        task_id = release_body.get("data", {}).get("task_id")
        if not task_id:
            raise RuntimeError("ACE-Step response did not include task_id")

        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            result_response = requests.post(
                ACE_QUERY_ENDPOINT, json={"task_id_list": [task_id]}, timeout=30
            )
            result_response.raise_for_status()
            body = result_response.json()
            if body.get("code") != 200:
                raise RuntimeError(body.get("error") or "ACE-Step result query failed")
            tasks = body.get("data") or []
            if not tasks:
                time.sleep(2)
                continue

            task = tasks[0]
            status = task.get("status", 0)
            if status == 2:
                raise RuntimeError(f"ACE-Step generation failed: {task.get('result')}")
            if status != 1:
                time.sleep(2)
                continue

            results = task.get("result", "[]")
            if isinstance(results, str):
                results = json.loads(results)
            if not results or not results[0].get("file"):
                raise RuntimeError("ACE-Step completed without an audio file")
            audio_url = urljoin(f"{ACE_API_BASE_URL}/", results[0]["file"])
            audio_response = requests.get(audio_url, timeout=120)
            audio_response.raise_for_status()
            if not audio_response.content:
                raise RuntimeError("ACE-Step returned an empty audio file")
            return audio_response

        raise TimeoutError(f"ACE-Step task {task_id} timed out")
    except (requests.RequestException, ValueError, RuntimeError, TimeoutError) as e:
        print(f"ACE-Step 1.5 API error: {e}")
        return None
