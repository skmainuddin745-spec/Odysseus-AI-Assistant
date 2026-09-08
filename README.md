# Odysseus — Local AI Research Assistant

> **A full-stack, privacy-first AI assistant with deep research, email, calendar, RAG, voice I/O, YouTube, and shell capabilities — running entirely on local hardware with multiple LLM backends.**

---

## Overview

**Odysseus** is a production-grade, self-hosted AI assistant built in Python (Flask + WebSockets). Unlike cloud-based AI tools, every model inference, document embedding, and tool call executes locally — no data leaves your machine.

### Core Capabilities

| Capability | Implementation |
|-----------|---------------|
| 🔍 **Deep Research** | Multi-step web search + synthesis via SearXNG |
| 📧 **Email** | Read, compose, send via IMAP/SMTP |
| 📅 **Calendar** | CalDAV sync — read/write events |
| 🧠 **RAG** | ChromaDB vector store + FastEmbed embeddings |
| 🗣️ **Voice I/O** | STT (Whisper) + TTS (Piper/Kokoro) |
| ▶️ **YouTube** | Search, transcribe, summarise videos |
| 💻 **Shell** | Sandboxed command execution |
| 📄 **Documents** | OCR, PDF parsing, semantic search |
| 👤 **Face recognition** | Local face-ID for access control |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser Client                    │
│          (HTML/CSS/JS — static/, templates/)         │
└─────────────────────┬───────────────────────────────┘
                      │ WebSocket + REST
┌─────────────────────▼───────────────────────────────┐
│                   Flask Application                  │
│            src/app.py  •  routes/*.py                │
│                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ AI Engine  │  │ Chat Handler │  │  BG Monitor │  │
│  │ai_interact.│  │chat_handler. │  │bg_monitor.py│  │
│  │    py      │  │     py       │  │             │  │
│  └─────┬──────┘  └──────┬───────┘  └──────┬──────┘  │
│        │                │                  │          │
│  ┌─────▼──────────────────────────────────▼──────┐   │
│  │              Services Layer                    │   │
│  │  search/  • stt/  • tts/  • memory/           │   │
│  │  youtube/ • shell/ • docs/ • faces/            │   │
│  └────────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │           Data + Storage                     │    │
│  │  ChromaDB (RAG)  •  SQLite  •  FastEmbed     │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## Key Source Files

### Core Application (`src/`)

| File | Lines | Description |
|------|-------|-------------|
| `ai_interaction.py` | ~1800 | LLM provider abstraction (Ollama, OpenAI, Anthropic), streaming, tool dispatch |
| `builtin_actions.py` | ~2600 | Full implementation of every built-in tool action |
| `deep_research.py` | ~900 | Multi-step research: query expansion → parallel search → synthesis |
| `chat_handler.py` | ~350 | WebSocket message routing, session management |
| `chat_processor.py` | ~370 | Streaming response processor + tool-call parser |
| `cleanup_service.py` | ~265 | Background job: prune old sessions, clear caches |
| `caldav_sync.py` | ~280 | CalDAV protocol client — event CRUD operations |
| `config.py` | ~240 | Centralised configuration with validation |
| `database.py` | ~80 | SQLite ORM wrapper |
| `auth_helpers.py` | ~135 | JWT-based authentication |

### Services (`services/`)

| Service | Key File | Description |
|---------|----------|-------------|
| Search | `search/service.py`, `content.py` | SearXNG query + content extraction + ranking |
| STT | `stt/stt_service.py` | Whisper/faster-whisper inference |
| TTS | `tts/tts_service.py` | Piper TTS + Kokoro + caching |
| YouTube | `youtube/youtube_handler.py` | yt-dlp + transcript extraction |
| Shell | `shell/service.py` | Sandboxed subprocess execution |
| Memory | `memory/` | ChromaDB RAG — embed, store, retrieve |

---

## Deep Research Pipeline

```python
# Simplified from src/deep_research.py
async def deep_research(query: str, max_rounds: int = 3):
    # 1. Query expansion — generate sub-questions
    sub_queries = await llm_expand(query, n=5)
    
    # 2. Parallel web search
    results = await asyncio.gather(*[
        searxng_search(q) for q in sub_queries
    ])
    
    # 3. Content extraction + reranking
    docs = [extract_content(r) for r in results]
    ranked = semantic_rerank(docs, query)
    
    # 4. Synthesis
    synthesis = await llm_synthesize(query, ranked[:10])
    return synthesis
```

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/yourusername/odysseus
cd odysseus
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml: set Ollama endpoint, email credentials, etc.

# Run
python app.py
# Open http://localhost:5000
```

---

## Technology Stack

- **Backend:** Python 3.11, Flask, Flask-SocketIO, aiohttp
- **AI/LLM:** Ollama (local), OpenAI API, Anthropic Claude API
- **RAG:** ChromaDB, FastEmbed (sentence transformers)
- **Voice:** OpenAI Whisper (STT), Piper TTS
- **Email/Calendar:** imaplib, smtplib, caldav
- **Database:** SQLite
- **Frontend:** Vanilla JS, WebSockets, CodeMirror editor

---

*AI Engineering · LLM · RAG · Self-hosted · Python · Flask · Privacy-first*
