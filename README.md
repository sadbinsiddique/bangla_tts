# Bangla TTS

Bangla text-to-speech using a VITS model and FastAPI.

## Setup

1. Create and activate a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

1. Install base dependencies:

```sh
pip install -r requirements.txt
```

If your `.venv` has permission restrictions in `site-packages`, install to the project-local vendor path instead:

```sh
python -m pip install --target ./vendor_tts -r requirements.txt
```

## Run API

```sh
source .venv/bin/activate
python app.py
```

The server starts on `192.168.0.1:3000`.

If `192.168.0.1` is not available on your machine/container, run:

```sh
API_HOST=0.0.0.0 API_PORT=3000 /home/siam/.vscode-remote-containers/dist/bangla_tts/.venv/bin/python app.py
```

Open the frontend in browser:

```sh
http://192.168.0.1:3000/
```

## Talk Pipeline (LLM -> TTS)

The app supports chat providers and converts assistant reply to speech using your TTS voice.

Set at least one provider key before using `/talk`:

```sh
export OPENAI_API_KEY="..."      # ChatGPT
export DEEPSEEK_API_KEY="..."    # DeepSeek
export GOOGLE_API_KEY="..."      # Gemini
export XAI_API_KEY="..."         # Grok
```

Optional model overrides:

```sh
export OPENAI_MODEL="gpt-4o-mini"
export DEEPSEEK_MODEL="deepseek-chat"
export GEMINI_MODEL="gemini-1.5-flash"
export XAI_MODEL="grok-2-latest"
```

Example `/talk` request:

```sh
curl -X POST http://192.168.0.1:3000/talk \
 -H "Content-Type: application/json" \
 -d '{"provider":"deepseek","prompt":"বাংলায় একটি ছোট গল্প লিখো।","gender":"female","save_dir":"output"}'
```

## Test API

```sh
curl -X POST http://192.168.0.1:3000/tts \
 -H "Content-Type: application/json" \
 -d '{"text":"আমি বাংলা বলতে পারি।","save_dir":"output","gender":"female"}'
```

For male voice, set `"gender":"male"`.

Response contains a generated wav file path in `audio_url`.

## Notes

- Models are downloaded automatically into `models/` on first run.
- Audio files are saved into the directory provided by `save_dir`.
