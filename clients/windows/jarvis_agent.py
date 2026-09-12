import os
import json
from dotenv import load_dotenv

load_dotenv()
from google import genai
from google.genai import types
from win_tools import WindowsController
from win_advanced_tools import SystemController
from jarvis_brain import BrainTools
from jarvis_memory import MemoryBrain, JARVIS_HUMAN_PROMPT

ALL_TOOLS = [
    WindowsController.launch_application,
    WindowsController.system_volume,
    WindowsController.window_management,
    WindowsController.type_text,
    SystemController.open_website,
    SystemController.terminate_process,
    SystemController.get_system_telemetry,
    BrainTools.web_search,
    BrainTools.get_weather
]

OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Opens Windows applications or web URLs (e.g. 'notepad', 'chrome', 'spotify', 'calculator', 'paint', 'explorer', 'vscode', 'youtube').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application or website name"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "system_volume",
            "description": "Adjusts Windows system audio volume (up, down, or mute).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["up", "down", "mute"], "description": "Volume action"},
                    "amount": {"type": "integer", "description": "Volume change percentage"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "window_management",
            "description": "Manages focused window state (minimize, maximize, or close active window).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["minimize", "maximize", "close"], "description": "Window action"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Types specified text onto the user's screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Opens website URL in specific browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Website URL or domain"},
                    "browser": {"type": "string", "description": "Browser name e.g. chrome"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminate_process",
            "description": "Terminates/kills a running process by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "process_name": {"type": "string", "description": "Process name to terminate"}
                },
                "required": ["process_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_telemetry",
            "description": "Gets current CPU, RAM, battery, and disk telemetry.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches the live web for facts, prices, news, or updates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Gets current live weather temperature and conditions for any city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    }
]


class JarvisAgent:
    def __init__(self, tts_speak_function):
        self.tts_speak_function = tts_speak_function
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.tool_map = {
            "launch_application": WindowsController.launch_application,
            "system_volume": WindowsController.system_volume,
            "window_management": WindowsController.window_management,
            "type_text": WindowsController.type_text,
            "open_website": SystemController.open_website,
            "terminate_process": SystemController.terminate_process,
            "get_system_telemetry": SystemController.get_system_telemetry,
            "web_search": BrainTools.web_search,
            "get_weather": BrainTools.get_weather,
        }

        # Try connecting to local Ollama daemon for offline AI & device control
        try:
            import ollama
            ollama.list()
            self.provider = "ollama"
            self.model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
            print(f"[Jarvis Agent]: Offline mode ACTIVE via local Ollama model '{self.model_name}'", flush=True)
        except Exception:
            if self.gemini_key and self.gemini_key != "your_gemini_api_key":
                try:
                    self.gclient = genai.Client(api_key=self.gemini_key)
                    self.chat = self.gclient.chats.create(
                        model="gemini-1.5-flash",
                        config=types.GenerateContentConfig(
                            system_instruction=JARVIS_HUMAN_PROMPT,
                            tools=ALL_TOOLS,
                            temperature=0.7
                        )
                    )
                    self.provider = "gemini"
                    print("[Jarvis Agent]: Using online Gemini AI model", flush=True)
                except Exception:
                    self.provider = "ollama"
                    self.model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
            elif self.openai_key:
                from openai import OpenAI
                self.o_client = OpenAI(api_key=self.openai_key)
                self.model_name = "gpt-4o-mini"
                self.provider = "openai"
                print("[Jarvis Agent]: Using OpenAI model", flush=True)
            else:
                self.provider = "ollama"
                self.model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

        self.conversation_history = [{"role": "system", "content": JARVIS_HUMAN_PROMPT}]

    def handle_user_query(self, transcript: str) -> None:
        """Processes user voice queries with memory context & multi-tool device control."""
        print(f">> User Said: '{transcript}'", flush=True)
        
        # Pull relevant memories about the user
        user_context = MemoryBrain.get_relevant_memories(transcript)
        spoken_reply = ""
        
        try:
            if self.provider == "gemini":
                prompt_input = transcript
                if user_context:
                    prompt_input = f"[Background context regarding user: {user_context}]\nUser said: {transcript}"
                response = self.chat.send_message(prompt_input)
                spoken_reply = (response.text or "").replace("*", "").replace("#", "").replace("_", "").strip()
            
            elif self.provider == "ollama":
                import ollama
                messages = list(self.conversation_history[-4:])
                if user_context:
                    messages.insert(-1, {"role": "system", "content": f"[Background user context: {user_context[:500]}]"})
                messages.append({"role": "user", "content": transcript[:1000]})
                self.conversation_history.append({"role": "user", "content": transcript[:1000]})

                res = ollama.chat(model=self.model_name, messages=messages, tools=OLLAMA_TOOLS)
                
                # Device Control Tool Calls Execution
                if hasattr(res.message, 'tool_calls') and res.message.tool_calls:
                    action_outputs = []
                    for tool_call in res.message.tool_calls:
                        func_name = tool_call.function.name
                        func_args = tool_call.function.arguments or {}
                        print(f"[Jarvis Local Tool Call]: {func_name}({func_args})", flush=True)
                        if func_name in self.tool_map:
                            try:
                                action_res = self.tool_map[func_name](**func_args)
                                action_outputs.append(str(action_res))
                                print(f"[Device Action Result]: {action_res}", flush=True)
                            except Exception as tex:
                                action_outputs.append(f"Execution note: {tex}")
                    spoken_reply = " ".join(action_outputs) if action_outputs else "Done, Sir."
                else:
                    spoken_reply = (res.message.content or "").replace("*", "").replace("#", "").replace("_", "").strip()

                self.conversation_history.append({"role": "assistant", "content": spoken_reply})

            else:
                # OpenAI pipeline
                turn_messages = list(self.conversation_history[-4:])
                if user_context:
                    safe_context = user_context[:500]
                    turn_messages.insert(-1, {
                        "role": "system", 
                        "content": f"[Background user context: {safe_context}]"
                    })
                
                safe_transcript = transcript[:1000]
                turn_messages.append({"role": "user", "content": safe_transcript})
                self.conversation_history.append({"role": "user", "content": safe_transcript})

                response = self.o_client.chat.completions.create(
                    model=self.model_name,
                    messages=turn_messages
                )
                spoken_reply = (response.choices[0].message.content or "").strip()

            # Enforce 6-turn sliding window history cap
            MAX_HISTORY = 6
            if len(self.conversation_history) > (MAX_HISTORY + 1):
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-MAX_HISTORY:]

            if not spoken_reply:
                spoken_reply = "At your service, Sir."

            print(f"[J.A.R.V.I.S.]: {spoken_reply}", flush=True)
            
            # Speak out response immediately
            self.tts_speak_function(spoken_reply)
            
            # Save memory context facts in background thread
            import threading
            threading.Thread(target=MemoryBrain.save_context_fact, args=(transcript, spoken_reply), daemon=True).start()

        except Exception as e:
            print(f"[Jarvis Agent Error]: {e}", flush=True)
            import traceback
            print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
            traceback.print_exc()
            print("="*60 + "\n", flush=True)
            fallback = f"My apologies Sir, error encountered: {e}"
            self.tts_speak_function(fallback)

