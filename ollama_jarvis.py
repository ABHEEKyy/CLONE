import json
import os
import sys
import time
import subprocess
import webbrowser
import psutil
from openai import OpenAI

# 1. Point directly to your local offline Ollama engine
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Required by client, but ignored by Ollama
)

MODEL_NAME = "llama3.1:8b"


from full_control_tools import UniversalController

# --- TOOL SCHEMAS FOR OLLAMA ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Opens any website, URL, or search term in a designated browser (brave, chrome, edge, firefox, or default).",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {"type": "string", "description": "Website or query (e.g. 'youtube.com', 'reddit', 'ai papers')"},
                    "browser": {
                        "type": "string",
                        "enum": ["brave", "chrome", "edge", "firefox", "default"],
                        "description": "The browser to open it in. Defaults to 'default'."
                    }
                },
                "required": ["site"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_file_or_folder",
            "description": "Searches for and opens a local file, document, video, or folder by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "File name, keyword, or folder name"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Opens any Windows desktop program, tool, or utility.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app (e.g. 'notepad', 'spotify', 'task manager')"}
                },
                "required": ["app_name"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., an operating system voice controller. "
    "MANDATORY INSTRUCTIONS:\n"
    "1. When the user asks to open an application, website, file, or folder, "
    "you MUST call the matching tool immediately.\n"
    "2. NEVER reply with text saying 'I will open it' or 'Opening now' without executing the tool call.\n"
    "3. For desktop programs (like 'notepad', 'calc'), call 'launch_application'.\n"
    "4. For local files, documents, or folders, call 'open_file_or_folder'."
)

conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]


def get_available_model():
    """Returns MODEL_NAME if available, else falls back to an available tool-capable model in local Ollama."""
    try:
        models = client.models.list()
        available_names = [m.id for m in models.data]
        if MODEL_NAME in available_names:
            return MODEL_NAME
        for name in available_names:
            if "llama" in name or "qwen" in name or "mistral" in name:
                return name
        if available_names:
            return available_names[0]
    except Exception:
        pass
    return MODEL_NAME


def run_jarvis_turn(user_command: str):
    global conversation_history
    active_model = get_available_model()

    # 1. Keep context strictly short (prevents repetition loops)
    clean_history = [conversation_history[0]] + conversation_history[-4:]
    clean_history.append({"role": "user", "content": user_command})

    try:
        # Step 1: Let Ollama decide the tool
        response = client.chat.completions.create(
            model=active_model,
            messages=clean_history,
            tools=TOOLS,
            tool_choice="auto"
        )
        msg = response.choices[0].message

    except Exception as e:
        import traceback
        print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
        traceback.print_exc()
        print("="*60 + "\n")
        conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
        return f"Disruption error: {e}"

    # Step 2: Handle Tool Calls Directly via UniversalController
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        f_name = tool_call.function.name
        
        try:
            args = tool_call.function.arguments
            if isinstance(args, str):
                args = json.loads(args)
        except Exception:
            args = {}

        print(f"[Executing Tool]: {f_name} with {args}")

        if hasattr(UniversalController, f_name):
            try:
                status = getattr(UniversalController, f_name)(**args)
                reply = f"At your service, Sir. {status}"
            except Exception as err:
                import traceback
                print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
                traceback.print_exc()
                print("="*60 + "\n")
                reply = f"System error executing {f_name}: {err}"
        else:
            reply = f"Command {f_name} is not mapped to my protocols."


    else:
        # Fallback Intent Matcher if LLM returned plain text instead of tool call
        cmd_lower = user_command.lower().strip()
        executed_fallback = False
        reply = ""

        if any(k in cmd_lower for k in ["open", "launch", "start", "run"]):
            # Check for website opening
            if any(domain in cmd_lower for domain in [".com", ".org", ".net", "youtube", "google", "github", "reddit", "netflix", "chatgpt"]):
                site = cmd_lower.replace("open ", "").replace("launch ", "").replace("start ", "").strip()
                status = UniversalController.open_website(site)
                reply = f"Right away, Sir. {status}"
                executed_fallback = True
            # Check for folder opening
            elif any(f_kw in cmd_lower for f_kw in ["folder", "directory", "document", "desktop", "downloads"]):
                folder = cmd_lower.replace("open ", "").replace("launch ", "").replace("folder", "").strip()
                status = UniversalController.open_file_or_folder(folder if folder else "desktop")
                reply = f"Right away, Sir. {status}"
                executed_fallback = True
            # App opening fallback
            else:
                app_target = cmd_lower.replace("open ", "").replace("launch ", "").replace("start ", "").replace("run ", "").strip()
                if app_target:
                    status = UniversalController.launch_application(app_target)
                    reply = f"Right away, Sir. {status}"
                    executed_fallback = True

        if not executed_fallback:
            reply = msg.content or "At your service, Sir."

    # Step 3: Clean up and store
    clean_reply = reply.replace("*", "").replace("#", "").strip()
    print(f"\nJ.A.R.V.I.S.: {clean_reply}\n")

    # Store turn cleanly without raw tool JSON objects
    conversation_history.append({"role": "user", "content": user_command})
    conversation_history.append({"role": "assistant", "content": clean_reply})

    return clean_reply


def speak(text: str):
    """Speaks through Windows SAPI5 TTS engine (silent in test mode)."""
    clean_text = text.strip()
    if not clean_text:
        return
    print(f"\nJ.A.R.V.I.S.: {clean_text}\n")
    if os.environ.get("HEADLESS_TEST") != "1":
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(clean_text)
        except Exception:
            try:
                import pyttsx3
                e = pyttsx3.init()
                e.say(clean_text)
                e.runAndWait()
            except Exception:
                pass


def listen_for_voice_commands():
    """Hands-free voice loop with single greeting and speaker echo decay."""
    import speech_recognition as sr

    wake_words = ["hello jarvis", "hey jarvis", "jarvis", "hi jarvis", "wake up"]
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    active_model = get_available_model()
    print("\n" + "=" * 60)
    print("⚡ J.A.R.V.I.S. VOICE CONTROLLER ONLINE")
    print(f"Active Model: {active_model}")
    print("Listening for wake word ('hello jarvis' / 'wake up')...")
    print("=" * 60 + "\n")

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"Microphone notice: {e}")
        return

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
    except Exception:
        pass

    while True:
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=5)

            try:
                speech = recognizer.recognize_google(audio).lower().strip()
                print(f"[Heard Voice]: '{speech}'")

                matched_wake = False
                command_remainder = ""

                for w in wake_words:
                    if w in speech:
                        matched_wake = True
                        command_remainder = speech.split(w, 1)[-1].strip()
                        break

                if matched_wake:
                    if command_remainder and len(command_remainder) > 2:
                        # Direct single-breath execution (e.g. "hello jarvis open notepad")
                        reply = run_jarvis_turn(command_remainder)
                        speak(reply)
                    else:
                        # Spoken wake greeting
                        speak("What may I help you with, Sir?")

                        # Allow speech output to completely finish before opening microphone
                        time.sleep(0.6)

                        print("\n⚡ [JARVIS ACTIVE]: Listening for your command...")
                        print("Waiting for command...")
                        start_time = time.time()
                        got_command = False

                        while (time.time() - start_time) < 25:
                            try:
                                remaining = int(25 - (time.time() - start_time))
                                if remaining <= 0:
                                    break
                                with mic as cmd_source:
                                    recognizer.adjust_for_ambient_noise(cmd_source, duration=0.2)
                                    cmd_audio = recognizer.listen(cmd_source, timeout=min(remaining, 6), phrase_time_limit=10)
                                cmd_text = recognizer.recognize_google(cmd_audio).lower().strip()
                                if cmd_text:
                                    print(f"[Command Received]: '{cmd_text}'")
                                    reply = run_jarvis_turn(cmd_text)
                                    speak(reply)
                                    got_command = True
                                    break
                            except sr.UnknownValueError:
                                continue
                            except sr.WaitTimeoutError:
                                continue

                        if not got_command:
                            print("No command detected. Returning to wake word listener...")

            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                pass

        except sr.WaitTimeoutError:
            continue
        except (KeyboardInterrupt, EOFError):
            print("\nExiting J.A.R.V.I.S. Voice Controller.")
            break


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "voice"
    if mode == "text":
        active = get_available_model()
        print(f"⚡ J.A.R.V.I.S. Text Mode (Active Model: {active}). Type exit to quit.")
        while True:
            try:
                cmd = input("You: ")
                if cmd.strip().lower() in ["exit", "quit"]:
                    break
                if cmd.strip():
                    run_jarvis_turn(cmd)
            except (KeyboardInterrupt, EOFError):
                break
    else:
        listen_for_voice_commands()
