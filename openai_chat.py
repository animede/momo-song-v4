import openai
from   openai import OpenAI
from   openai import AsyncOpenAI
import asyncio
import os

# OpenAI APIから応答を取得する関数 ログなし（非同期版）
async def chat_req(client, user_msg, role):
    messages = [
        {"role": "system", "content": role},
        {"role": "user", "content": user_msg}
    ]
    # await を使って coroutine の実行結果を取得
    completion = await client.chat.completions.create(
        model=os.getenv(
            "LLM_MODEL",
            "./models/gemma4-31B/gemma-4-31B-it-Q4_K_M.gguf",
        ),
        messages=messages,
    )
    return completion.choices[0].message.content
