#!/usr/bin/env python
"""
Implement a phony Ollama server that returns pre-generated random
prompts in sequence. Prompts are uploaded as JSON with the "/prompts"
API call, then retrieved one-by-one with the Ollama "/api/chat" call.
"feed.sh" is a small script to upload a file of one-line prompts,
which does:
    cat *.txt | jq -R . | jq -s . |
        curl -s -S -m 120 -X POST --json @- http://localhost:8000/prompt

I use this to feed my generated prompts into SwarmUI's GUI via the
MagicPrompt extension.
"""

import time
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import random

app = FastAPI()

responses = list()

@app.get("/")
async def root(request: Request):
    """stub"""
    return {
        "result": "success"
    }

@app.get("/api/tags")
async def api_tags(request: Request):
    """phony model list for Ollama API"""
    return {
        "models": [
            { 
                "id": "botbot",
                "name": "botbot",
                "model": "botbot",
                "version": "1.0.4",
                "modified_at": "2024-01-02T03:04:05Z",
                "size": 8675309,
                "digest": "aaabacadae...",
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "parameter_size": "1B",
                    "quantization_level": "Q4_0"
                }
            },
            { 
                "id": "botbot2",
                "name": "botbot2",
                "model": "botbot2",
                "version": "1.0.4",
                "modified_at": "2024-01-02T03:04:05Z",
                "size": 8675309,
                "digest": "aAabacadae...",
                "details": {
                    "format": "gguf",
                    "family": "llama",
                    "parameter_size": "1B",
                    "quantization_level": "Q4_0"
                }
            }

        ]
    }

@app.post("/api/chat")
async def api_chat(request: Request):
    """
    implement Ollama chat result that returns the first item
    from the list of uploaded prompts, deleting it once used.
    The non-streaming response is used by both chat and prompt modes.
    """
    body = await request.body()
    return {
        "stream": False,
        "model": "botbot",
        "created_at": "2026-01-02T03:04:05Z",
        "message": {
            "role": "assistant",
            "content": responses.pop(0) if len(responses)>0 else "no loaded prompts"
        },
        "done": True,
        "total_duration": 1,
        "load_duration": 1,
        "prompt_eval_count": 1,
        "prompt_eval_duration": 1,
        "eval_count": 1,
        "eval_duration": 1
    }


@app.post("/prompt")
async def upload_prompts(request: Request):
    """
    fill the response list with one-line responses:
        feed.sh file ...
    or 
        cat prompts.txt | jq -R .  | jq -s . | curl -s -S -m 3600 -X POST --json @- http://localhost:8000/prompt
    """
    body = await request.json()
    if isinstance(body, list):
        for prompt in body:
            responses.append(prompt)
    else:
        responses.append(body)
    return {
        "responses": responses
    }

@app.get("/count")
async def count_prompts(request: Request):
    """return current number of loaded prompts"""
    return len(responses)

@app.get("/clear")
async def clear_prompts(request: Request):
    """clear current list of loaded prompts"""
    responses.clear()
    return "empty!"

# NOTE: server is exposed on network for remote SwarmUI use;
# don't do this in on a public network.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
