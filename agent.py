import logging
import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool
from livekit.plugins import google
from livekit.plugins.turn_detector.multilingual import MultilingualModel


_TASHKEEL_RE = re.compile(r"[\u064B-\u065F\u0670]")

def _strip_tashkeel(text: str) -> str:
    return _TASHKEEL_RE.sub("", text)

logger = logging.getLogger("yaquod-agent")


STARTER_GREETING = (
    "You are Yaquod (يَقُودْ). Greet the user warmly in one short Egyptian Arabic sentence, then ask how you can help.\n"
    "TASHKEEL: Add full tashkeel to every word.\n"
    "RESPONSE: Keep responses short, warm, and conversational."
)

LANGUAGE_CONFIGS = {
    "ar": {"stt_lang": "ar-EG", "tts_lang": "ar-XA", "voice_name": "ar-XA-Chirp3-HD-Aoede"},
    "en": {"stt_lang": "en-US", "tts_lang": "en-US", "voice_name": "en-US-Chirp3-HD-Aoede"},
}

DEFAULT_LANG = "ar"

ALLOWED_ACTIONS = {
    "ac_on",
    "ac_off",
    "set_level",

    "window_open",
    "window_close",

    "music_play",
    "music_pause",
    "set_volume",
    "next_track",
    "previous_track",

    "reading_light_on",
    "reading_light_off",

    "change_destination",
    "cancel_destination",

    "safe_stop",
}


class Assistant(Agent):

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "<role>\n"
                "You are Yaquod (يَقُود), a friendly voice assistant inside an autonomous vehicle.\n"
                "</role>\n\n"
                "<languages>\n"
                "- Support Egyptian Arabic (اللهجة المصرية) and English.\n"
                "- Detect the user's language on every turn.\n"
                "- If it differs from the current language, call switch_language.\n"
                "- Always reply in the language the user just used.\n"
                "</languages>\n"
                "\n"
                "<vehicle_actions>\n"
                "You ONLY control predefined vehicle actions.\n"
                "You must NEVER execute arbitrary commands.\n"
                "If user requests a vehicle action, call vehicle_action tool.\n\n"

                "Allowed actions:\n"
                "- Climate: ac_on, ac_off, set_level\n"
                "- Windows: window_open, window_close\n"
                "- Media: music_play, music_pause, set_volume, next_track, previous_track\n"
                "- Lights: reading_light_on, reading_light_off\n"

                "- Navigation: change_destination, cancel_destination\n"
                "- Safety: safe_stop\n\n"

                "NEVER execute:\n"
                "- accelerate\n"
                "- brake manually\n"
                "- steer\n"
                "- lane change\n"
                "- override autonomous driving\n"
                "- disable safety systems\n"
                "</vehicle_actions>\n\n"

                "<tone>\n"
                "Keep responses short, natural, and spoken.\n"
                "</tone>\n"
                "\n"
                "<arabic_rule>\n"
                "TASHKEEL: Every Arabic word MUST have full tashkeel "
                "(fatha, kasra, damma, sukun, shadda). Without it the TTS "
                "mispronounces words.\n"
                "</arabic_rule>"
            )
        )
        self._current_lang = DEFAULT_LANG


    async def transcription_node(self, text, model_settings):
        async for chunk in text:
            if isinstance(chunk, str):
                yield _strip_tashkeel(chunk)
            else:
                yield chunk


    @function_tool
    async def switch_language(self, context: RunContext, language: str) -> str:
        config = LANGUAGE_CONFIGS.get(language)

        if not config:
           return f"Unsupported language '{language}'. Supported: ar, en."

        if language == self._current_lang:
            return f"Already using {language}"

        session = context.session
        logger.info(f"Switching language: {self._current_lang} -> {language}")

        session.tts.update_options(
            language=config["tts_lang"],
            voice_name=config["voice_name"],
        )

        self._current_lang = language

        return f"Switched to {language}"


    @function_tool
    async def vehicle_action(
        self,
        context: RunContext,
        action: str,
        parameters: dict | None = None,
    ) -> str:

        # Safety whitelist check
        if action not in ALLOWED_ACTIONS:
            return "This action is not allowed."

        payload = {
            "vehicle_id": "vehicle_001",
            "action": action,
            "parameters": parameters or {}
        }

        logger.info("Vehicle Action:\n%s", json.dumps(payload, indent=2))

        try:
            response = requests.post(
                "http://localhost:8000/api/vehicle/action",
                json=payload,
                timeout=5,
            )

            if response.ok:
                return f"Executed {action}"
            else:
                return "Vehicle API error"

        except Exception as e:
            logger.error(f"API error: {e}")
            return "Vehicle system unavailable"


server = AgentServer()

@server.rtc_session(agent_name="yaquod")
async def my_agent(ctx: agents.JobContext):
    default_config = LANGUAGE_CONFIGS[DEFAULT_LANG]

    session = AgentSession(
        # Speech-to-Text
        stt=google.STT(
            languages=[default_config["stt_lang"], LANGUAGE_CONFIGS["en"]["stt_lang"]],
            detect_language=True,
            model="chirp_3",
            location="us",
        ),

        # LLM
        llm=google.LLM(model="gemini-3.1-flash-lite"),

        # Text-to-Speech
        tts=google.TTS(
            language=default_config["tts_lang"],
            voice_name=default_config["voice_name"],
        ),

        turn_detection=MultilingualModel(),
    )

    await session.start(room=ctx.room, agent=Assistant())
    await session.generate_reply(instructions=STARTER_GREETING)

if __name__ == "__main__":
    agents.cli.run_app(server)