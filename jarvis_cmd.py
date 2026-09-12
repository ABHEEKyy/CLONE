import sys
import win32event
import win32api
import winerror
import os
import re
import json
from openai import OpenAI
from command_engine import execute_open_site, execute_launch_app, execute_kill_task

# Unique system mutex identifier to prevent ghost background instances
MUTEX_NAME = "Global\\JARVIS_VOICE_ASSISTANT_SINGLE_INSTANCE"
mutex = win32event.CreateMutex(None, False, MUTEX_NAME)

if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    print("⚠️ An instance of J.A.R.V.I.S. is already active. Exiting duplicate process.")
    sys.exit(0)

# Connect to local Ollama instance with 30s timeout
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
    timeout=30.0  # Prevents cognitive matrix timeout drops
)
MODEL_NAME = "llama3.1:8b"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_site",
            "description": "Opens a website or link in a designated web browser (brave, chrome, edge, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {"type": "string", "description": "Domain or shortcut (e.g., 'youtube', 'github')"},
                    "browser": {"type": "string", "enum": ["brave", "chrome", "edge", "firefox", "default"]}
                },
                "required": ["site"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Opens an installed Windows desktop application (e.g., 'notepad', 'calculator', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app"}
                },
                "required": ["app_name"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., an operating system command dispatcher. "
    "MANDATORY: When asked to open, launch, or run an application or website, "
    "you MUST use the provided tools. Never provide a plain conversational reply for actions."
)

history = [{"role": "system", "content": SYSTEM_PROMPT}]

def fallback_intent_runner(text: str) -> str:
    """Fail-safe: Executes commands via regex if the local LLM skips tool-calling."""
    lower = text.lower().strip()

    # Browser intent check: "open [site] in/on [browser]"
    browser_match = re.search(r'(?:open|launch)\s+(.+?)\s+(?:in|on)\s+(brave|chrome|edge|firefox)', lower)
    if browser_match:
        site, browser = browser_match.groups()
        return execute_open_site(site, browser)

    # General site check
    if any(lower.startswith(k) for k in ["open youtube", "launch youtube", "open yt", "launch yt", "open google"]):
        site = "youtube" if "yt" in lower or "youtube" in lower else "google"
        return execute_open_site(site, "default")

    # Application launch check: "open [app]", "launch [app]"
    app_match = re.search(r'(?:open|launch|start)\s+([a-zA-Z0-9\s]+)', lower)
    if app_match:
        target = app_match.group(1).strip()
        if target not in ["a website", "the internet"]:
            return execute_launch_app(target)

    return ""

def process_command(user_cmd: str):
    global history
    print(f"\n[Command Received]: \"{user_cmd}\"")

    # 1. Ask Ollama
    try:
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[history[0], {"role": "user", "content": user_cmd}],
            tools=TOOLS,
            tool_choice="auto"
        )
        msg = res.choices[0].message
    except Exception as e:
        import traceback
        print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
        traceback.print_exc()
        print("="*60 + "\n")
        msg = None

    action_taken = False

    # 2. Check if Ollama triggered a tool
    if msg and msg.tool_calls:
        for tool in msg.tool_calls:
            f_name = tool.function.name
            try:
                args = tool.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
            except Exception:
                args = {}
            print(f"[Tool Calling Engine]: Running {f_name}({args})")
            
            try:
                if f_name == "open_site":
                    print(execute_open_site(**args))
                    action_taken = True
                elif f_name == "launch_app":
                    print(execute_launch_app(**args))
                    action_taken = True
            except Exception as err:
                import traceback
                print("\n" + "="*20 + " REAL PYTHON TRACEBACK " + "="*20)
                traceback.print_exc()
                print("="*60 + "\n")


    # 3. Fail-safe execution if model only returned text
    if not action_taken:
        fallback_res = fallback_intent_runner(user_cmd)
        if fallback_res:
            print(f"[Fast-Dispatch]: {fallback_res}")
        else:
            reply = msg.content if msg else "Command not recognized."
            print(f"J.A.R.V.I.S.: {reply}")

if __name__ == "__main__":
    print("=====================================================")
    print("      J.A.R.V.I.S. CMD TERMINAL CONTROLLER ONLINE    ")
    print("=====================================================")
    
    while True:
        try:
            cmd = input("\nJ.A.R.V.I.S. > ")
            if cmd.strip().lower() in ["exit", "quit", "q"]:
                break
            if cmd.strip():
                process_command(cmd)
        except KeyboardInterrupt:
            break
