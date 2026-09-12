import os
import sys
import time
import subprocess
import shutil
import numpy as np
import pyaudio
import pyttsx3
import winsound
import ollama
from faster_whisper import WhisperModel
import openwakeword
from openwakeword.model import Model

# Safely handle stdio for Windows background daemons
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
elif hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import tempfile
import atexit
import psutil

# Global active instance lockfile (prevents listener from opening duplicate windows)
LOCK_FILE = os.path.join(tempfile.gettempdir(), "jarvis_active_assistant.lock")

try:
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
except Exception:
    pass

@atexit.register
def _cleanup_lock_file():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

# ==========================================
# 1. VOICE ENGINE SETUP (Offline SAPI5)
# ==========================================
try:
    tts_engine = pyttsx3.init('sapi5')
    voices = tts_engine.getProperty('voices')
    if voices:
        tts_engine.setProperty('voice', voices[0].id)
    tts_engine.setProperty('rate', 185)  # Natural speaking pace
except Exception as e:
    tts_engine = None
    print(f"TTS Init Warning: {e}")

def speak(text: str):
    """Speaks text out loud through Windows speakers and prints to screen."""
    clean_text = text.replace("*", "").replace("#", "").replace('"', "'").strip()
    if not clean_text:
        return

    print(f"\nJ.A.R.V.I.S.: {clean_text}\n")
    sys.stdout.flush()

    # 1. Thread-safe Native Windows SAPI5 Speech Engine (win32com)
    try:
        import win32com.client
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(clean_text)
        return
    except Exception as e1:
        print(f"[SAPI5 Voice Error]: {e1}")

    # 2. Pyttsx3 Speech Engine Fallback
    try:
        if tts_engine:
            tts_engine.say(clean_text)
            tts_engine.runAndWait()
            return
    except Exception:
        pass

    # 3. PowerShell System.Speech Synthesis Fallback (Guaranteed Windows audio output)
    try:
        ps_cmd = f'Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak("{clean_text}")'
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=10)
    except Exception as e3:
        print(f"[PowerShell Voice Error]: {e3}")

# ==========================================
# 2. LOCAL AI INITIALIZATION
# ==========================================
RATE = 16000
CHUNK = 1280
WAKE_THRESHOLD = 0.1  # Set to 0.1 for high sensitivity

import urllib.request

def ensure_ollama_service_running():
    """Checks if local Ollama server is responding on port 11434; launches 'ollama serve' if down."""
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5)
    except Exception:
        print("⚡ [Ollama Auto-Start]: Service not active. Launching 'ollama serve'...")
        try:
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.Popen("ollama serve", shell=True, creationflags=creationflags)
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ [Ollama Service Error]: {e}")

def get_available_ollama_model():
    ensure_ollama_service_running()
    try:
        models_res = ollama.list()
        model_list = models_res.get('models', []) if isinstance(models_res, dict) else getattr(models_res, 'models', [])
        names = []
        for m in model_list:
            if isinstance(m, dict):
                names.append(m.get('name', ''))
            elif hasattr(m, 'model'):
                names.append(getattr(m, 'model', ''))
            elif hasattr(m, 'name'):
                names.append(getattr(m, 'name', ''))

        for preferred in ["qwen2.5:3b", "llama3.1:8b", "llama3.2", "qwen2.5"]:
            for name in names:
                if preferred in name:
                    return name
        if names:
            return names[0]
    except Exception:
        pass
    return "qwen2.5:3b"

print("⏳ Initializing local neural models...")

# Whisper STT model (Fast load with 4 CPU threads)
stt_model = WhisperModel("tiny.en", device="cpu", compute_type="int8", cpu_threads=4)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
print(f"Active Local LLM Model: {OLLAMA_MODEL}")

_oww_model = None
def get_oww_model():
    global _oww_model
    if _oww_model is None:
        try:
            openwakeword.utils.download_models()
        except Exception:
            pass
        _oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    return _oww_model

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, frames_per_buffer=CHUNK)

# ==========================================
# 3. WINDOWS SYSTEM CONTROLLERS
# ==========================================
def find_all_matching_files(query_name: str) -> list:
    """Finds all matching files, shortcuts (.lnk), or executables (.exe) across system and workspace directories."""
    raw = query_name.lower().replace("the ", "").replace("file ", "").replace("shortcut ", "").replace("folder ", "").replace("game ", "").replace("app ", "").strip()
    compressed = raw.replace(" ", "")

    user_home = os.path.expanduser("~")
    workspace_root = os.getcwd()
    search_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, r"OneDrive\Desktop"),
        r"C:\Users\Public\Desktop",
        os.path.join(user_home, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        workspace_root,
        os.path.abspath(os.path.join(workspace_root, "..")),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, r"OneDrive\Documents"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "Pictures"),
        os.path.join(user_home, r"OneDrive\Pictures"),
        os.path.join(user_home, "Videos"),
    ]

    matches = []
    seen_paths = set()

    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        try:
            for root, dirs, files in os.walk(s_dir):
                for item in files + dirs:
                    full_path = os.path.abspath(os.path.join(root, item))
                    if full_path in seen_paths:
                        continue

                    item_name_lower = item.lower()
                    base_name, ext = os.path.splitext(item_name_lower)
                    
                    clean_item_name = base_name.replace(" - shortcut", "").replace("-shortcut", "").replace("(shortcut)", "").replace("_", " ").replace("-", " ").strip()
                    clean_compressed = clean_item_name.replace(" ", "")

                    words_in_query = [w for w in raw.split() if len(w) > 1]
                    is_match = False

                    if raw == clean_item_name or compressed == clean_compressed or raw == item_name_lower:
                        is_match = True
                    elif raw in clean_item_name or compressed in clean_compressed or raw in item_name_lower or clean_compressed in compressed:
                        is_match = True
                    elif words_in_query and all(w in clean_item_name or w in clean_compressed for w in words_in_query):
                        is_match = True

                    if is_match:
                        matches.append((full_path, item, ext))
                        seen_paths.add(full_path)

                if root.count(os.sep) - s_dir.count(os.sep) >= 3:
                    del dirs[:]
        except Exception:
            continue

    return matches


def launch_application(app_name: str) -> str:
    """Launches system applications, desktop shortcuts, documents, folders, or custom files with partial name matching. Pass the exact target requested by the user."""
    raw_cmd = app_name.lower().strip()
    for prefix in ["open ", "run ", "launch ", "execute ", "start "]:
        if raw_cmd.startswith(prefix):
            raw_cmd = raw_cmd[len(prefix):].strip()

    # Handle 'open X in Y' or 'open X with Y'
    if " in " in raw_cmd or " with " in raw_cmd:
        sep = " in " if " in " in raw_cmd else " with "
        parts = raw_cmd.split(sep, 1)
        file_q, app_q = parts[0].strip(), parts[1].strip()

        file_matches = find_all_matching_files(file_q)
        if not file_matches:
            return f"Could not find any file matching '{file_q}'."

        matched_file = file_matches[0][0]
        app_targets = {
            "notepad": "notepad.exe",
            "code": "code",
            "vscode": "code",
            "vs code": "code",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "paint": "mspaint.exe",
            "calc": "calc.exe"
        }
        target_app = app_targets.get(app_q, app_q)
        try:
            subprocess.Popen(f'start "" {target_app} "{matched_file}"', shell=True)
            return f"Opening '{os.path.basename(matched_file)}' in {app_q}."
        except Exception as e:
            try:
                os.startfile(matched_file)
                return f"Opening '{os.path.basename(matched_file)}' with default program."
            except Exception as ex:
                return f"Failed to open file: {ex}"

    raw = raw_cmd.replace("the ", "").replace("app", "").replace("application", "").strip()
    compressed = raw.replace(" ", "")

    print(f"[FILE_SEARCH]: Searching partial/full matches for '{raw}'...")

    system_targets = {
        "notepad": "notepad.exe",
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "taskmgr": "taskmgr.exe",
        "taskmanager": "taskmgr.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "explorer": "explorer.exe",
        "fileexplorer": "explorer.exe",
        "settings": "ms-settings:",
        "paint": "mspaint.exe",
        "chrome": "chrome.exe",
        "brave": "brave.exe",
        "edge": "msedge.exe",
        "steam": "steam://",
        "spotify": "spotify:",
        "discord": "discord:",
        "whatsapp": "whatsapp:",
        "telegram": "telegram:",
        "vlc": "vlc.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "powerpoint": "powerpnt.exe",
        "code": "code",
        "vscode": "code",
        "vs code": "code"
    }

    # 1. Direct Alias Check
    target = system_targets.get(compressed, system_targets.get(raw, None))
    if target:
        try:
            os.startfile(target)
            return f"Opening {raw} application."
        except Exception:
            pass

    # 2. Search Desktop & System for matches
    matches = find_all_matching_files(raw)

    if not matches:
        exe_path = shutil.which(f"{compressed}.exe") or shutil.which(f"{raw}.exe")
        if exe_path:
            try:
                subprocess.Popen([exe_path], shell=False)
                return f"Opening {raw} executable."
            except Exception:
                pass

        try:
            subprocess.Popen(f'start "" "{raw}"', shell=True)
            return f"Dispatched start signal for {raw}."
        except Exception:
            return f"I was unable to locate an app, shortcut, or file matching '{raw}'."

    # Sort matches so .lnk shortcuts and .exe executables rank first, regular files second, and directories last
    lnk_matches = [m for m in matches if m[2] == ".lnk"]
    exe_matches = [m for m in matches if m[2] in [".exe", ".bat", ".cmd", ".ps1"]]
    file_matches = [m for m in matches if not os.path.isdir(m[0]) and m[2] not in [".lnk", ".exe", ".bat", ".cmd", ".ps1"]]
    dir_matches = [m for m in matches if os.path.isdir(m[0])]

    ordered_matches = lnk_matches + exe_matches + file_matches + dir_matches

    chosen_path, chosen_name, chosen_ext = ordered_matches[0]
    item_kind = "shortcut" if chosen_ext == ".lnk" else "application" if chosen_ext in [".exe", ".bat", ".cmd", ".ps1"] else "directory" if os.path.isdir(chosen_path) else "file"
    try:
        os.startfile(chosen_path)
        return f"Found matching item for {raw}. Opening {chosen_name} ({item_kind})."
    except Exception as e:
        return f"Could not launch {chosen_name}: {e}"

        return f"Found matching items for {raw}. Opening {chosen_name} ({item_kind})."
    except Exception as e:
        return f"Could not launch {chosen_name}: {e}"


def web_search(query: str) -> str:
    """Searches the live web and internet for real-time news, facts, current events, and general knowledge."""
    clean_q = query.strip()
    if not clean_q:
        return "Please specify a topic or question to search."

    print(f"🌐 [Web Search]: Searching live internet for '{clean_q}'...")

    # 1. Real-time DDGS / DuckDuckGo search first (critical for current leaders, news, scores, dates)
    try:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(clean_q, max_results=3))
        except Exception:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(clean_q, max_results=3))

        if results:
            snippets = [f"{r.get('title', '')}: {r.get('body', '')}" for r in results if r.get('body')]
            if snippets:
                return "\n".join(snippets[:3])
    except Exception as e:
        print(f"DDGS search note: {e}")

    # 2. Wikipedia search fallback for general encyclopedia topics
    wiki_res = wikipedia_search(clean_q)
    if wiki_res and "No summary available" not in wiki_res and "could not find" not in wiki_res.lower() and len(wiki_res) > 40:
        return f"According to Wikipedia: {wiki_res}"

    # 3. HTTP REST DuckDuckGo HTML snippet scraping fallback
    try:
        import urllib.request, urllib.parse, re
        q_enc = urllib.parse.quote(clean_q)
        req = urllib.request.Request(
            f"https://html.duckduckgo.com/html/?q={q_enc}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        html = urllib.request.urlopen(req, timeout=5).read().decode("utf-8", errors="ignore")
        snippets = re.findall(r'result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
        clean_snips = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets if s.strip()]
        if clean_snips:
            return " ".join(clean_snips[:2])
    except Exception:
        pass

    return f"I performed a search for '{clean_q}', but could not retrieve live snippets at this moment."


def wikipedia_search(query: str) -> str:
    """Queries Wikipedia encyclopedia REST API for facts, biographies, history, science, and definitions."""
    try:
        import urllib.request, urllib.parse, json
        clean_q = query.replace("wikipedia", "").replace("who is", "").replace("what is", "").replace("tell me about", "").strip()
        if not clean_q:
            clean_q = query.strip()

        # Step 1: Search Wikipedia for matching page title
        search_enc = urllib.parse.quote(clean_q)
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_enc}&format=json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "JarvisAssistant/1.0 (contact@jarvis.ai)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        search_results = data.get("query", {}).get("search", [])
        if not search_results:
            return f"Wikipedia has no exact article for '{clean_q}'."

        best_title = search_results[0]["title"]
        page_enc = urllib.parse.quote(best_title.replace(" ", "_"))

        # Step 2: Fetch Page Summary
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_enc}"
        req_sum = urllib.request.Request(summary_url, headers={"User-Agent": "JarvisAssistant/1.0 (contact@jarvis.ai)"})
        with urllib.request.urlopen(req_sum, timeout=5) as resp_sum:
            sum_data = json.loads(resp_sum.read().decode("utf-8"))

        extract = sum_data.get("extract", "").strip()
        if extract:
            return f"{best_title}: {extract}"
        return f"Found article '{best_title}' on Wikipedia."

    except Exception as e:
        return f"Wikipedia lookup error: {str(e)}"


BTECH_SYLLABUS = {
    "1. Partial Differential Equations (PDE)": [
        "Formation of PDE & Direct Integration",
        "Linear & Non-linear First Order Equations (Charpit's Method)",
        "Homogeneous & Non-homogeneous Linear Equations"
    ],
    "2. Applications of PDEs": [
        "Method of Separation of Variables",
        "Heat, Wave & Laplace Equation Solutions",
        "Elliptic, Parabolic & Hyperbolic Canonical Forms"
    ],
    "3. Fourier Series & Transforms": [
        "Fourier Series, Dirichlet Conditions, Half Range Series & Parseval's Identity",
        "Fourier Integrals & Fourier Sine/Cosine Transforms"
    ],
    "4. Semiconductor Devices & Diode Circuits": [
        "PN Junction, Drift/Diffusion Capacitance & Current",
        "Zener, Schottky, LED, Solar Cell & Voltage Regulator",
        "Rectifiers, Clipping & Clamping Circuits"
    ],
    "5. BJT & Transistor Amplifiers": [
        "BJT Construction, CB/CE/CC Configurations & Operating Points",
        "Transistor Biasing, Thermal Stability & RC Coupled Amplifiers"
    ],
    "6. FETs & Operational Amplifiers": [
        "JFET Volt-Ampere Characteristics, MOSFET (Enhancement & Depletion)",
        "Op-Amp 741 Architecture, CMRR, Virtual Ground, Inverting & Non-inverting Amplifiers"
    ],
    "7. Basic Digital Electronics & Computer Architecture": [
        "Combinational Logic: Decoders, Encoders, Multiplexers, Adders & ALU",
        "Basic Computer Organization: Registers, Instruction Cycle & Control Units",
        "CPU Design: Stack/Register Organization, Addressing Modes & RISC vs CISC",
        "Memory Organization: RAM/ROM, Cache Mapping, Virtual Memory & Pipelining"
    ],
    "8. Data Structures & Algorithms (DSA)": [
        "Arrays, Pointers, Algorithm Complexity & Sparse Matrices",
        "Stacks, Queues, Polish Expressions & Recursion",
        "Singly/Doubly/Circular Linked Lists & Polynomial Arithmetic",
        "Trees: Binary Trees, AVL Trees, Threaded Trees, B-Trees & Graph Traversals (DFS/BFS)",
        "Sorting (Quick, Merge, Heap) & Searching (Hashing, Collision Resolution)"
    ],
    "9. Python for Machine Learning & Data Science": [
        "NumPy Vectorization, Pandas Dataframes & Data Preprocessing",
        "Data Visualization: Matplotlib & Seaborn, EDA & Scikit-learn Pipelines",
        "Supervised Learning: Regression (Linear, Ridge, Lasso) & Classification (SVM, Naive Bayes, KNN)",
        "Decision Trees & Ensemble Methods (Random Forest, Gradient Boosting)",
        "Unsupervised Learning: K-Means, Hierarchical Clustering & PCA"
    ],
    "10. Object-Oriented Programming with C++": [
        "OOP Concepts: Abstraction, Encapsulation, Inheritance & Polymorphism",
        "Classes, Objects, Constructors, Destructors & Friend Functions",
        "Inheritance: Virtual Base Classes & Ambiguity Resolution",
        "Polymorphism: Function/Operator Overloading & Virtual Functions",
        "Exception Handling, File Streams, Templates & Standard Template Library (STL)"
    ],
    "11. Master Coding Languages & Frameworks": [
        "Python, C, C++, Java, Rust, Go, JavaScript & TypeScript",
        "React, Next.js, Node.js, Express, Django, FastAPI & Flask",
        "SQL (PostgreSQL, MySQL) & NoSQL (MongoDB, Redis, Vector DBs)",
        "Assembly Language, MATLAB, R & Julia Programming"
    ],
    "12. Advanced Computer Science & Artificial Intelligence": [
        "Deep Learning: Neural Networks, CNNs, RNNs, Transformers & LLMs",
        "Computer Vision & Natural Language Processing (NLP)",
        "System Design, Distributed Systems, Cloud Computing (AWS/Docker/K8s) & Microservices",
        "Cybersecurity, Cryptography, Blockchain & Ethical Hacking"
    ],
    "13. Advanced Science & Frontier Engineering": [
        "Quantum Computing, Quantum Mechanics & Qiskit",
        "Astrophysics, Aerospace Engineering & Orbital Mechanics",
        "Robotics, Control Systems & Embedded IoT Engineering",
        "Bioinformatics, Computational Biology & Nanotechnology"
    ]
}

def is_syllabus_menu_request(text: str) -> bool:
    """Returns True ONLY if the user is asking to view the learning menu/syllabus/topics list, without specifying a topic to teach."""
    cmd = text.lower().strip()
    
    # Explicit menu / syllabus commands
    menu_phrases = [
        "show syllabus", "what can i learn", "learning menu", "curriculum",
        "list topics", "show topics", "btech syllabus", "show subjects",
        "what subjects", "what topics", "learning options", "show menu", "list menu",
        "learning curriculum", "academy menu"
    ]
    if any(p in cmd for p in menu_phrases):
        return True
        
    # Generic teach/learn phrases without a specific topic attached
    import re
    cleaned = re.sub(r'[^a-z0-9\s]', '', cmd).strip()
    generic_only = [
        "teach me", "i want to learn", "want to learn", "teach me something",
        "what can you teach me", "teach me anything", "teach", "learn"
    ]
    if cleaned in generic_only:
        return True
        
    return False

def extract_topic_name(text: str) -> str:
    """Extracts target topic name from commands like 'Teach me, teach me astrophysics' -> 'astrophysics'."""
    import re
    cmd = text.strip()
    # Strip common leading verbs and phrases
    pattern = r'^(teach me|i want to learn|want to learn|please teach me|tell me about|explain|lesson on|teach)\b'
    cleaned = re.sub(pattern, '', cmd, flags=re.IGNORECASE).strip()
    cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.strip(",.?!:; ")
    return cleaned if cleaned else text

def list_learning_topics(category: str = "all") -> str:
    """Lists all available subjects and modules available for learning in B.Tech, Coding, and Advanced Science."""
    print("\n==========================================================================")
    print("      📚 J.A.R.V.I.S. MASTER ACADEMY & B.TECH CURRICULUM MENU      ")
    print("==========================================================================")
    
    lines = []
    for subject, modules in BTECH_SYLLABUS.items():
        print(f"\n🔹 {subject}:")
        lines.append(f"• {subject}")
        for mod in modules:
            print(f"   └─ {mod}")
            
    print("\n==========================================================================")
    print("💡 SAY OR TYPE ANY TOPIC NAME ABOVE OR ASK ABOUT ANY SUBJECT ON EARTH!")
    print("==========================================================================\n")
    sys.stdout.flush()

    return "What would you like to learn today, Sir? Here are the main areas available:\n1. B.Tech Mathematics & PDEs\n2. Semiconductor Devices & Electronics\n3. Digital Electronics & Computer Architecture\n4. Data Structures & Algorithms (DSA)\n5. Python, Machine Learning & Data Science\n6. Object-Oriented Programming with C++\n7. Master Coding Languages (Python, C++, Java, Rust, JavaScript, Go, SQL, MATLAB)\n8. Advanced AI, System Design & Cloud Computing\n9. Advanced Science (Quantum Computing, Robotics, Astrophysics)\n\nWhich of these would you like to dive into today, Sir?"

def teach_topic(topic_name: str) -> str:
    """Provides a detailed, comprehensive educational lesson on any specific coding or B.Tech topic requested by the user."""
    print(f"📖 [J.A.R.V.I.S. Teaching Mode]: Preparing deep lesson on '{topic_name}'...")
    # Perform web/wikipedia search to supplement deep lesson data
    res = wikipedia_search(topic_name)
    if not res or "could not find" in res.lower():
        res = web_search(topic_name)
    return res


def open_website(site: str, browser: str = "default") -> str:
    clean_site = site.lower().strip()
    shortcuts = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://www.github.com",
        "reddit": "https://www.reddit.com"
    }
    url = shortcuts.get(clean_site, clean_site if clean_site.startswith("http") else f"https://{clean_site}.com")
    
    b_map = {"brave": "brave.exe", "chrome": "chrome.exe", "edge": "msedge.exe"}
    b_target = b_map.get(browser.lower().strip())

    if b_target:
        subprocess.Popen(f'start {b_target} "{url}"', shell=True)
        return f"Opening {site} in {browser.title()}."
    else:
        import webbrowser
        webbrowser.open(url)
        return f"Opening {site}."

active_language = "English"

def set_language(target_language: str) -> str:
    """Explicitly switches J.A.R.V.I.S.'s persistent spoken & written language until changed again."""
    global active_language
    clean_lang = target_language.strip().title()
    active_language = clean_lang
    return f"Language switched to {active_language}. I will now speak and respond exclusively in {active_language} until you change it again, Sir."

AVAILABLE_FUNCS = {
    "launch_application": launch_application,
    "open_website": open_website,
    "set_language": set_language,
    "web_search": web_search,
    "wikipedia_search": wikipedia_search,
    "list_learning_topics": list_learning_topics,
    "teach_topic": teach_topic
}

TOOLS_LIST = [launch_application, open_website, set_language, web_search, wikipedia_search, list_learning_topics, teach_topic]

# ==========================================
# 4. SPEECH RECOGNITION & PIPELINE
# ==========================================
def record_command(silence_limit_seconds=2.5, max_seconds=35.0) -> bytes:
    print("🎙️ Listening (Waiting up to 35 seconds for your command)...")
    sys.stdout.flush()
    frames = []
    silent_chunks = 0
    max_silent = int((RATE / CHUNK) * silence_limit_seconds)
    total_allowed = int((RATE / CHUNK) * max_seconds)
    speech_detected = False

    for _ in range(total_allowed):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

        frame_np = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(frame_np.astype(np.float32) ** 2))

        if rms > 130:
            speech_detected = True

        if rms < 130:
            silent_chunks += 1
            if speech_detected and silent_chunks > max_silent and len(frames) > int((RATE / CHUNK) * 1.5):
                break
        else:
            silent_chunks = 0

    return b"".join(frames)

def transcribe_audio(audio_bytes: bytes) -> str:
    if len(audio_bytes) < RATE * 0.5 * 2:
        return ""
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    # Auto-detect ANY spoken language (English, Hindi, Spanish, French, German, Japanese, Chinese, etc.)
    segments, _ = stt_model.transcribe(audio_data, vad_filter=True)
    return " ".join([s.text for s in segments]).strip()

# Multilingual Conversational Memory State
conversation_history = [
    {
        "role": "system",
        "content": (
            "You are J.A.R.V.I.S., a multilingual, highly intelligent, warm, and witty AI companion. "
            "CURRENT PERSISTENT SPOKEN LANGUAGE: English. "
            "You understand and speak all languages fluently. Respond in the required persistent language. "
            "Keep verbal responses clear, natural, and concise (1 to 3 sentences max for smooth spoken dialogue). "
            "When asked to open desktop apps, websites, or system actions, execute the appropriate tool."
        )
    }
]

def check_language_switch(user_text: str) -> str:
    """Detects explicit language switch commands in user input."""
    global active_language
    lower = user_text.lower()
    lang_map = {
        "hindi": "Hindi",
        "spanish": "Spanish",
        "french": "French",
        "german": "German",
        "japanese": "Japanese",
        "chinese": "Chinese",
        "russian": "Russian",
        "italian": "Italian",
        "portuguese": "Portuguese",
        "english": "English"
    }
    if any(k in lower for k in ["switch language", "change language", "speak in", "talk in", "speak hindi", "speak spanish", "speak french", "speak german"]):
        for k, v in lang_map.items():
            if k in lower:
                active_language = v
                return f"Language changed to {active_language}. I will speak in {active_language} from now on, Sir."
    return None

def fallback_dispatcher(command_text: str) -> str:
    """Fallback dispatcher for common launch, learning, and general knowledge search commands."""
    cmd = command_text.lower().strip()

    # Explicit menu/syllabus check
    if is_syllabus_menu_request(command_text):
        return list_learning_topics()

    # Specific topic teaching fallback
    if any(k in cmd for k in ["teach me", "want to learn", "lesson on", "explain"]):
        topic = extract_topic_name(command_text)
        if topic and not is_syllabus_menu_request(topic):
            return teach_topic(topic)

    # General Knowledge / Web search triggers (who, what, where, when, why, how, tell me, explain, search, etc.)
    search_prefixes = [
        "who is ", "who was ", "what is ", "what was ", "what are ", "where is ", "where was ",
        "when is ", "when was ", "why is ", "why does ", "how does ", "how is ", "how to ",
        "tell me about ", "tell me ", "explain ", "define ", "search for ", "search ", "wikipedia ",
        "find info on ", "lookup ", "details on ", "history of ", "meaning of "
    ]
    if any(cmd.startswith(prefix) or f" {prefix.strip()} " in f" {cmd} " for prefix in search_prefixes) or "?" in cmd:
        return web_search(command_text)

    for verb in ["open ", "launch ", "start ", "run "]:
        if cmd.startswith(verb):
            target = cmd[len(verb):].strip()
            if target:
                return launch_application(target)
    if any(k in cmd for k in ["notepad", "note pad"]):
        return launch_application("notepad")
    if any(k in cmd for k in ["calc", "calculator"]):
        return launch_application("calc")
    if any(k in cmd for k in ["cmd", "command prompt", "terminal"]):
        return launch_application("cmd")
    if any(k in cmd for k in ["task manager", "taskmgr"]):
        return launch_application("taskmgr")
    if any(k in cmd for k in ["explorer", "file explorer"]):
        return launch_application("explorer")
    if "settings" in cmd:
        return launch_application("settings")
    if "chrome" in cmd:
        return launch_application("chrome")
    if "brave" in cmd:
        return launch_application("brave")
    if "edge" in cmd:
        return launch_application("edge")
    if "youtube" in cmd:
        return open_website("youtube")
    if "github" in cmd:
        return open_website("github")
    if "google" in cmd:
        return open_website("google")
    return None

def process_command(user_text: str):
    global conversation_history, active_language
    print(f"🗣️ You: \"{user_text}\"")
    sys.stdout.flush()

    # 1. Check for manual language switch command
    sw_msg = check_language_switch(user_text)
    if sw_msg:
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": sw_msg})
        speak(sw_msg)
        return

    # 2. Check ONLY for learning menu / syllabus requests (NOT specific topics)
    if is_syllabus_menu_request(user_text):
        res_text = list_learning_topics()
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": res_text})
        speak(res_text)
        return

    # 3. Check for direct open/launch action commands first (prevents LLM substituting requested target)
    lower_text = user_text.lower().strip()
    for verb in ["open ", "launch ", "start ", "run "]:
        if lower_text.startswith(verb):
            target = lower_text[len(verb):].strip()
            if target:
                res = launch_application(target)
                conversation_history.append({"role": "user", "content": user_text})
                conversation_history.append({"role": "assistant", "content": res})
                speak(res)
                return

    # 4. Dynamically update system prompt with current active language & phonetic rules
    if active_language.lower() == "hindi":
        lang_rule = (
            "CURRENT REQUIRED SPOKEN LANGUAGE: Hindi. "
            "CRITICAL FORMAT RULE FOR HINDI: Write ALL Hindi responses strictly in clean Romanized Hinglish script using the English/Latin alphabet "
            "(for example: 'Main bilkul theek hoon Sir, aap bataiye main aapki kya madad kar sakta hoon?'). "
            "Do NOT output Devanagari characters (like हिंदी) so the voice synthesizer speaks naturally and smoothly."
        )
    else:
        lang_rule = f"CURRENT REQUIRED SPOKEN LANGUAGE: {active_language}. You MUST answer, speak, and converse STRICTLY in {active_language}."

    conversation_history[0] = {
        "role": "system",
        "content": (
            f"You are J.A.R.V.I.S., a world-class AI master engineer, expert computer scientist, and witty companion. "
            f"You possess exhaustive, expert-level knowledge across EVERY programming language (Python, C, C++, Java, Rust, Go, JavaScript, TypeScript, Assembly, SQL, HTML/CSS, Kotlin, Swift, MATLAB, R, Haskell, etc.) "
            f"and every B.Tech Engineering domain (Data Structures & Algorithms, Operating Systems, Computer Networks, DBMS, System Design, Mathematics, AI/ML, Electrical/Electronics, Software Engineering). "
            f"{lang_rule} "
            f"When answering technical, B.Tech academic, or coding questions, provide authoritative, precise, crystal-clear, and practical answers. "
            f"Keep all verbal responses clear, natural, and concise (1 to 3 sentences max for smooth spoken dialogue). "
            f"When asked to open desktop apps, websites, or system actions, execute the appropriate tool using the exact target requested."
        )
    }

    # Add user speech turn to memory
    conversation_history.append({"role": "user", "content": user_text})

    # Keep conversation memory bounded (system prompt + last 12 turns)
    if len(conversation_history) > 13:
        conversation_history = [conversation_history[0]] + conversation_history[-12:]

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=conversation_history,
            tools=TOOLS_LIST
        )
        msg = response.message

        if msg.tool_calls:
            for tool in msg.tool_calls:
                fn_name = tool.function.name
                fn_args = tool.function.arguments
                if isinstance(fn_args, str):
                    import json
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}
                if fn_name in AVAILABLE_FUNCS:
                    result = AVAILABLE_FUNCS[fn_name](**fn_args)
                    
                    if fn_name in ["web_search", "wikipedia_search", "teach_topic"]:
                        # Synthesize live internet/wikipedia/educational context with LLM into natural 2-4 spoken sentences
                        synth_msgs = [
                            {
                                "role": "system",
                                "content": (
                                    f"You are J.A.R.V.I.S., a world-class AI master professor and engineer. "
                                    f"Teach an engaging, clear, and comprehensive lesson to the user on their request: '{user_text}'. "
                                    f"Use the following reference material if helpful: '{result}'. "
                                    "State core principles, key concepts, and practical insights directly in 2-4 clear spoken sentences."
                                )
                            }
                        ]
                        try:
                            synth_res = ollama.chat(model=OLLAMA_MODEL, messages=synth_msgs)
                            spoken_summary = synth_res.message.content.strip()
                            conversation_history.append({"role": "assistant", "content": spoken_summary})
                            speak(spoken_summary)
                        except Exception:
                            conversation_history.append({"role": "assistant", "content": result})
                            speak(result)
                    else:
                        conversation_history.append({"role": "assistant", "content": result})
                        speak(result)
        else:
            fb = fallback_dispatcher(user_text)
            if fb:
                gk_keywords = [
                    "who is", "who was", "what is", "what was", "what are", "where is", "where was",
                    "when is", "when was", "why is", "why does", "how does", "how is", "how to",
                    "tell me", "explain", "define", "search", "wikipedia", "find info", "history", "meaning", "name"
                ]
                if any(kw in user_text.lower() for kw in gk_keywords) or "?" in user_text:
                    # Synthesize fallback web results using local LLM
                    try:
                        synth_msgs = [
                            {
                                "role": "system",
                                "content": (
                                    f"STRICT FACTUAL MANDATE: Answer the user's question '{user_text}' EXCLUSIVELY using this live internet search data: '{fb}'. "
                                    "CRITICAL RULE: DO NOT use your internal training memory if it contradicts these live web search results. "
                                    "State the exact names, current officeholders, dates, and numbers directly from the search snippets in 1-2 clear spoken sentences."
                                )
                            }
                        ]
                        synth_res = ollama.chat(model=OLLAMA_MODEL, messages=synth_msgs)
                        spoken_summary = synth_res.message.content.strip()
                        conversation_history.append({"role": "assistant", "content": spoken_summary})
                        speak(spoken_summary)
                    except Exception:
                        conversation_history.append({"role": "assistant", "content": fb})
                        speak(fb)
                else:
                    conversation_history.append({"role": "assistant", "content": fb})
                    speak(fb)
            else:
                # If LLM didn't call tool and fallback didn't catch, execute web search automatically for questions
                if any(kw in user_text.lower() for kw in ["who", "what", "where", "when", "why", "how", "tell", "explain", "search", "know", "history", "name"]) or "?" in user_text:
                    live_info = web_search(user_text)
                    try:
                        synth_msgs = [
                            {
                                "role": "system",
                                "content": (
                                    f"STRICT FACTUAL MANDATE: Answer the user's question '{user_text}' EXCLUSIVELY using this live web search data: '{live_info}'. "
                                    "CRITICAL RULE: IGNORE your pre-trained internal memory. State the exact names, current leaders, dates, and facts from the live search text directly in 1-2 spoken sentences."
                                )
                            }
                        ]
                        synth_res = ollama.chat(model=OLLAMA_MODEL, messages=synth_msgs)
                        spoken_summary = synth_res.message.content.strip()
                        conversation_history.append({"role": "assistant", "content": spoken_summary})
                        speak(spoken_summary)
                    except Exception:
                        conversation_history.append({"role": "assistant", "content": live_info})
                        speak(live_info)
                else:
                    reply = msg.content or "I am right here with you, Sir."
                    conversation_history.append({"role": "assistant", "content": reply})
                    speak(reply)

    except Exception as e:
        print(f"Ollama execution error: {e}")
        fb = fallback_dispatcher(user_text)
        if fb:
            conversation_history.append({"role": "assistant", "content": fb})
            speak(fb)
        else:
            err_reply = "My apologies, Sir, I encountered a brief glitch processing that request."
            speak(err_reply)


# ==========================================
# 5. CONTINUOUS ASSISTANT LOOP
# ==========================================
def start_voice_assistant():
    try:
        from jarvis_banner import print_jarvis_banner
        print_jarvis_banner()
    except Exception:
        pass
    speak("All systems initialized. I am listening, Sir.")
    try:
        import winsound
        winsound.Beep(1200, 150)
    except Exception:
        pass

    print("\n🎙️ Listening for your command...")
    sys.stdout.flush()

    # Immediately capture spoken command on launch
    audio = record_command()
    text = transcribe_audio(audio)
    if text:
        process_command(text)

    print("\nListening for 'Hey Jarvis'...")
    sys.stdout.flush()

    oww = get_oww_model()
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)

            score = oww.predict(frame).get("hey_jarvis", 0.0)

            if score >= WAKE_THRESHOLD:
                # Wake acknowledgment sound & greeting
                try:
                    winsound.Beep(1100, 120)
                except Exception:
                    pass
                oww.reset()

                greeting = "What may I help you with, Sir?"
                speak(greeting)

                # Capture voice command
                audio = record_command()
                text = transcribe_audio(audio)


                if text:
                    process_command(text)
                else:
                    speak("Say something, Sir.")

                # Reset audio ring buffer to prevent self-triggering
                oww.reset()
                for _ in range(int(RATE / CHUNK * 0.8)):
                    stream.read(CHUNK, exception_on_overflow=False)
                
                print("\nListening for 'Hey Jarvis'...")
                sys.stdout.flush()

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Assistant Loop Error]: {e}")
            oww.reset()
            time.sleep(0.5)

    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == "__main__":
    start_voice_assistant()
