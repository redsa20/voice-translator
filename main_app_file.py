import asyncio, time, logging
from collections import deque
from datetime import datetime

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import WS_PATH, MERGE_WAIT
from audio_capture import audio_chunk_producer
from transcriber import Transcriber
from translator import translate
from subtitle_writer import SubtitleWriter
from websocket_manager import ConnectionManager

logging.basicConfig(level=logging.INFO)
app      = FastAPI(title="RT-Translator-Pro")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/", StaticFiles(directory="static", html=True), name="static")

manager      = ConnectionManager()
transcriber  = Transcriber()
writer       = SubtitleWriter()

audio_q:asyncio.Queue = asyncio.Queue(5)
text_q :asyncio.Queue = asyncio.Queue(5)

stats = {"start":datetime.now(),"segments":0,"translations":0,"last":None}

# ───── Smart merge buffer ─────
class Merger:
    def __init__(self, wait:float):
        self.buf=deque(); self.last=time.time(); self.wait=wait
    def add(self,t:str):
        now=time.time(); self.buf.append(t)
        if now-self.last>self.wait or t.endswith((".","?","!")):
            out=" ".join(self.buf); self.buf.clear(); self.last=now; return out

merger=Merger(MERGE_WAIT)

@app.websocket(WS_PATH)
async def websocket(ws:WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()  # keep-alive
    except Exception: pass
    finally: await manager.disconnect(ws)

@app.on_event("startup")
async def start_tasks():
    loop=asyncio.get_event_loop()
    loop.create_task(audio_chunk_producer(audio_q))
    loop.create_task(transcriber_worker())
    loop.create_task(translator_worker())

async def transcriber_worker():
    while True:
        audio=await audio_q.get()
        eng  =await transcriber.transcribe(audio)
        stats["segments"]+=1; stats["last"]=datetime.now().isoformat()
        await text_q.put(eng)

async def translator_worker():
    while True:
        eng=await text_q.get()
        merged=merger.add(eng)
        if merged:
            heb=await translate(merged)
            await manager.broadcast(heb)
            await writer.add(merged, heb)
            stats["translations"]+=1

# ───── Monitoring ─────
@app.get("/stats"); async def _stats():
    now=datetime.now()
    return {"uptime":(now-stats["start"]).total_seconds(),
            "active_ws":len(manager.active),**stats}

@app.get("/readyz"); async def _ready(): return {"ok":True}
