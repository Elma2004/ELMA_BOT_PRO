import json
import random
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.metrics import dp
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, FadeTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

BASE = Path(__file__).resolve().parent
BRAIN_FILE = BASE / "subconscient_elma.json"
CONFIG_FILE = BASE / "vic_config.json"
BOT_PASSWORD = "Elma2026"

THEMES = {
    "bleu": {"bg": [0.025,0.055,0.12,1], "panel":[0.055,0.10,0.20,0.96], "accent":[0.08,0.55,1,1], "accent2":[0.35,0.82,1,1], "text":[0.94,0.98,1,1], "muted":[0.58,0.70,0.84,1]},
    "violet": {"bg": [0.075,0.035,0.13,1], "panel":[0.12,0.065,0.20,0.96], "accent":[0.58,0.28,1,1], "accent2":[0.85,0.55,1,1], "text":[0.97,0.95,1,1], "muted":[0.72,0.63,0.84,1]},
    "vert": {"bg": [0.02,0.10,0.08,1], "panel":[0.04,0.17,0.13,0.96], "accent":[0.08,0.78,0.48,1], "accent2":[0.45,1,0.70,1], "text":[0.94,1,0.97,1], "muted":[0.57,0.80,0.70,1]},
    "rouge": {"bg": [0.12,0.035,0.045,1], "panel":[0.20,0.06,0.08,0.96], "accent":[1,0.22,0.25,1], "accent2":[1,0.58,0.38,1], "text":[1,0.95,0.95,1], "muted":[0.84,0.64,0.65,1]},
    "sombre": {"bg": [0.018,0.018,0.022,1], "panel":[0.06,0.06,0.07,0.98], "accent":[0.48,0.52,0.60,1], "accent2":[0.76,0.80,0.88,1], "text":[0.94,0.94,0.96,1], "muted":[0.60,0.62,0.68,1]},
}

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)

def normalize_text(value):
    value = str(value).replace("’", "'").replace("`", "'")
    value = value.lower().strip()
    value = "".join(c for c in unicodedata.normalize("NFD", value)
                    if unicodedata.category(c) != "Mn")
    value = re.sub(r"[!?.,;:()\[\]{}\"/\\]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def similarity(a, b):
    a, b = normalize_text(a), normalize_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    score = SequenceMatcher(None, a, b).ratio()
    if a in b or b in a:
        score = max(score, 0.88)
    return score

def parse_brain_text(text):
    rules = []
    errors = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" not in line:
            errors.append(f"Ligne {line_no}: il manque =>")
            continue
        left, right = line.split("=>", 1)
        triggers = [x.strip() for x in left.split("|") if x.strip()]
        responses = [x.strip() for x in right.split("||") if x.strip()]
        if not triggers:
            errors.append(f"Ligne {line_no}: aucun mot-clé.")
        elif not responses:
            errors.append(f"Ligne {line_no}: aucune réponse.")
        else:
            rules.append({"declencheurs": triggers, "reponses": responses})
    return rules, errors

def brain_to_text(brain):
    lines = [
        "# CERVEAU ELMA — format : mot-clé | mot-clé => réponse || réponse",
        "# Les commentaires commencent par #.",
        ""
    ]
    for rule in brain.get("regles", []):
        lines.append(" | ".join(rule.get("declencheurs", [])) + " => " + " || ".join(rule.get("reponses", [])))
    return "\n".join(lines)

def find_local_answer(brain, message):
    best = None
    best_score = 0.0
    threshold = float(brain.get("parametres", {}).get("similarite_minimum", 0.78))
    for rule in brain.get("regles", []):
        for trigger in rule.get("declencheurs", []):
            score = similarity(message, trigger)
            if score > best_score:
                best_score = score
                best = rule
    for item in brain.get("connaissances_apprises", []):
        question = item.get("question_normalisee", item.get("question", ""))
        score = similarity(message, question)
        if score > best_score:
            best_score = score
            best = {"reponses": item.get("reponses", [])}
    if best and best_score >= threshold and best.get("reponses"):
        return random.choice(best["reponses"])
    return None

def ask_gemini(brain, message):
    cfg = load_json(CONFIG_FILE, {})
    key = str(cfg.get("ai_key", "")).strip()
    model = cfg.get("model", "gemini-2.0-flash")
    if not key:
        return None
    prompt = (
        "Tu es ELMA, un répondeur SMS naturel. Comprends les petites fautes, "
        "les accents manquants, la ponctuation et les emojis. Ne corrige jamais "
        "l'utilisateur et ne lui parle pas de ses fautes. Réponds directement, "
        "clairement et naturellement en français. Question : " + message
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        r = requests.post(url, params={"key": key},
                          json={"contents":[{"parts":[{"text":prompt}]}]},
                          timeout=20)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None

def answer_message(message, learn=True):
    brain = load_json(BRAIN_FILE, {"regles": [], "connaissances_apprises": [], "parametres": {}})
    local = find_local_answer(brain, message)
    if local:
        return local
    if not learn or not brain.get("parametres", {}).get("apprentissage_gemini", True):
        return "🤖 Je n’ai pas encore appris cette réponse."
    answer = ask_gemini(brain, message)
    if answer:
        if brain.get("parametres", {}).get("conserver_reponses_gemini", True):
            norm = normalize_text(message)
            found = None
            for item in brain.setdefault("connaissances_apprises", []):
                if similarity(norm, item.get("question_normalisee", "")) >= 0.88:
                    found = item
                    break
            if found:
                if answer not in found.setdefault("reponses", []):
                    found["reponses"].append(answer)
            else:
                brain["connaissances_apprises"].append({
                    "question": message,
                    "question_normalisee": norm,
                    "reponses": [answer]
                })
            save_json(BRAIN_FILE, brain)
        return answer
    return "🤖 Je n’ai pas encore la réponse. Tu peux l’ajouter dans mon cerveau ou configurer Gemini."

class Card(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.padding = dp(14)
        with self.canvas.before:
            self.bg_color = Color(*app.theme["panel"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._sync, size=self._sync)
    def _sync(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

class ModernButton(Button):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.background_normal = ""
        self.background_down = ""
        self.background_color = [0,0,0,0]
        self.color = app.theme["text"]
        self.font_size = dp(15)
        self.bold = True
        self.size_hint_y = None
        self.height = dp(50)
        with self.canvas.before:
            self.c = Color(*app.theme["accent"])
            self.r = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync)
    def _sync(self, *_):
        self.r.pos = self.pos
        self.r.size = self.size

class BaseScreen(Screen):
    def build_bg(self):
        with self.canvas.before:
            self.bg = Color(*self.manager.app.theme["bg"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
            self.glow = Color(*self.manager.app.theme["accent"])
            self.orb1 = Ellipse(pos=(self.width-dp(120), self.height-dp(150)), size=(dp(190),dp(190)))
            self.glow.a = 0.10
        self.bind(pos=self._sync_bg, size=self._sync_bg)
    def _sync_bg(self, *_):
        self.rect.pos = self.pos; self.rect.size = self.size
        self.orb1.pos = (self.width-dp(120), self.height-dp(150))

class SplashScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        box = BoxLayout(orientation="vertical", padding=dp(28), spacing=dp(8))
        box.add_widget(Label(text="ELMA", font_size=dp(48), bold=True, color=self.manager.app.theme["accent2"]))
        box.add_widget(Label(text="BOT PRO", font_size=dp(22), bold=True, color=self.manager.app.theme["text"]))
        box.add_widget(Label(text="🧠 Votre cerveau numérique intelligent", color=self.manager.app.theme["muted"], font_size=dp(14)))
        self.add_widget(box)
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "home"), 1.2)

class HomeScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        root.add_widget(Label(text="ELMA BOT PRO", font_size=dp(28), bold=True, color=self.manager.app.theme["text"], size_hint_y=None, height=dp(55)))
        root.add_widget(Label(text="🧠 Un répondeur qui apprend avec toi", color=self.manager.app.theme["accent2"], size_hint_y=None, height=dp(32)))
        card = Card(self.manager.app, orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(120))
        card.add_widget(Label(text="Bienvenue, créateur 👋\nGère le cerveau, teste ELMA et personnalise son apparence.", color=self.manager.app.theme["text"]))
        root.add_widget(card)
        for label, screen in [
            ("🧠  Cerveau ELMA", "brain"),
            ("💬  Tester le répondeur", "bot"),
            ("⚙️  Paramètres", "settings"),
            ("ℹ️  Informations", "info"),
        ]:
            root.add_widget(ModernButton(self.manager.app, text=label, on_release=lambda x, s=screen: setattr(self.manager, "current", s)))
        root.add_widget(Label(text="ELMA • 3.0", color=self.manager.app.theme["muted"], size_hint_y=None, height=dp(30)))
        self.add_widget(root)

class BrainScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="🧠 CERVEAU ELMA", font_size=dp(23), bold=True, color=self.manager.app.theme["text"], size_hint_y=None, height=dp(45)))
        root.add_widget(Label(text="mot-clé | mot-clé => réponse || réponse", color=self.manager.app.theme["muted"], size_hint_y=None, height=dp(28)))
        self.editor = TextInput(text=brain_to_text(self.manager.app.brain), multiline=True,
                                background_color=self.manager.app.theme["panel"], foreground_color=self.manager.app.theme["text"],
                                cursor_color=self.manager.app.theme["accent2"], padding=dp(12))
        root.add_widget(self.editor)
        buttons = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        buttons.add_widget(ModernButton(self.manager.app, text="💾 VALIDER", on_release=self.save_brain))
        buttons.add_widget(ModernButton(self.manager.app, text="↻ RECHARGER", on_release=lambda x: self.reload_brain()))
        buttons.add_widget(ModernButton(self.manager.app, text="← RETOUR", on_release=lambda x: setattr(self.manager, "current", "home")))
        root.add_widget(buttons)
        self.status = Label(text="", color=self.manager.app.theme["muted"], size_hint_y=None, height=dp(34))
        root.add_widget(self.status)
        self.add_widget(root)
    def save_brain(self, *_):
        rules, errors = parse_brain_text(self.editor.text)
        if errors:
            self.status.text = "❌ " + " | ".join(errors[:3])
            return
        self.manager.app.brain["regles"] = rules
        save_json(BRAIN_FILE, self.manager.app.brain)
        self.status.text = "✅ Cerveau enregistré avec succès."
    def reload_brain(self):
        self.manager.app.brain = load_json(BRAIN_FILE, self.manager.app.brain)
        self.editor.text = brain_to_text(self.manager.app.brain)
        self.status.text = "↻ Cerveau rechargé."

class BotScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        root.add_widget(Label(text="💬 RÉPONDEUR ELMA", font_size=dp(22), bold=True, color=self.manager.app.theme["text"], size_hint_y=None, height=dp(45)))
        self.password = TextInput(hint_text="Mot de passe", password=True, multiline=False, size_hint_y=None, height=dp(46))
        root.add_widget(self.password)
        self.unlock_btn = ModernButton(self.manager.app, text="🔐 Déverrouiller", on_release=self.unlock)
        root.add_widget(self.unlock_btn)
        self.question = TextInput(hint_text="Écris un message à ELMA…", multiline=True, disabled=True, size_hint_y=None, height=dp(90))
        root.add_widget(self.question)
        root.add_widget(ModernButton(self.manager.app, text="🤖 DEMANDER À ELMA", on_release=self.ask))
        self.answer = Label(text="ELMA attend ton message…", color=self.manager.app.theme["text"], halign="left", valign="top")
        self.answer.bind(size=lambda x, v: setattr(x, "text_size", (v[0], None)))
        root.add_widget(self.answer)
        root.add_widget(ModernButton(self.manager.app, text="← RETOUR", on_release=lambda x: setattr(self.manager, "current", "home")))
        self.add_widget(root)
    def unlock(self, *_):
        if self.password.text == BOT_PASSWORD:
            self.question.disabled = False
            self.answer.text = "🔓 Accès autorisé. ELMA est prêt."
        else:
            self.answer.text = "❌ Mot de passe incorrect."
    def ask(self, *_):
        if self.question.disabled:
            self.answer.text = "🔐 Déverrouille d’abord ELMA."
            return
        msg = self.question.text.strip()
        if not msg:
            return
        self.answer.text = "🤖 ELMA réfléchit…"
        Clock.schedule_once(lambda dt: setattr(self.answer, "text", answer_message(msg)), 0.05)

class SettingsScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        app = self.manager.app
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        root.add_widget(Label(text="⚙️ PARAMÈTRES", font_size=dp(23), bold=True, color=app.theme["text"], size_hint_y=None, height=dp(45)))
        root.add_widget(Label(text="🎨 Choisis la couleur d’ELMA", color=app.theme["muted"], size_hint_y=None, height=dp(30)))
        for key, label in [("bleu","🔵 Bleu ELMA"),("violet","🟣 Violet"),("vert","🟢 Vert"),("rouge","🔴 Rouge"),("sombre","🌑 Sombre")]:
            root.add_widget(ModernButton(app, text=label, on_release=lambda x, k=key: app.set_theme(k)))
        brain = app.brain.setdefault("parametres", {})
        self.learn = ModernButton(app, text=("🧠 Apprentissage Gemini : ON" if brain.get("apprentissage_gemini", True) else "🧠 Apprentissage Gemini : OFF"), on_release=self.toggle_learning)
        root.add_widget(self.learn)
        root.add_widget(Label(text="Les changements de thème sont sauvegardés automatiquement.", color=app.theme["muted"], size_hint_y=None, height=dp(40)))
        root.add_widget(ModernButton(app, text="← RETOUR", on_release=lambda x: setattr(self.manager, "current", "home")))
        self.add_widget(root)
    def toggle_learning(self, *_):
        p = self.manager.app.brain.setdefault("parametres", {})
        p["apprentissage_gemini"] = not p.get("apprentissage_gemini", True)
        save_json(BRAIN_FILE, self.manager.app.brain)
        self.on_enter()

class InfoScreen(BaseScreen):
    def on_enter(self):
        self.clear_widgets()
        app = self.manager.app
        root = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(10))
        root.add_widget(Label(text="ℹ️ ELMA BOT PRO", font_size=dp(25), bold=True, color=app.theme["text"], size_hint_y=None, height=dp(50)))
        root.add_widget(Label(text="🤖 Répondeur intelligent\n🧠 Cerveau modifiable\n✨ Apprentissage Gemini\n📱 Réponse SMS Android\n🎨 Thèmes personnalisables\n\nCréateur : Monsieur Kiomba Somwe Jenovic Elma\nCréé le : 29/08/2026", color=app.theme["text"]))
        root.add_widget(ModernButton(app, text="← RETOUR", on_release=lambda x: setattr(self.manager, "current", "home")))
        self.add_widget(root)

class ElmaBotApp(App):
    theme_name = "bleu"
    theme = THEMES["bleu"]
    brain = {}

    def build(self):
        self.title = "ELMA BOT PRO"
        self.brain = load_json(BRAIN_FILE, {})
        cfg = load_json(CONFIG_FILE, {})
        self.theme_name = cfg.get("theme", "bleu")
        self.theme = THEMES.get(self.theme_name, THEMES["bleu"])
        sm = ScreenManager(transition=FadeTransition(duration=0.18))
        for name, cls in [("splash",SplashScreen),("home",HomeScreen),("brain",BrainScreen),("bot",BotScreen),("settings",SettingsScreen),("info",InfoScreen)]:
            screen = cls(name=name)
            sm.add_widget(screen)
            screen.build_bg()
        sm.app = self
        Clock.schedule_once(lambda dt: setattr(sm, "current", "splash"), 0)
        return sm

    def set_theme(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        self.theme = THEMES[name]
        cfg = load_json(CONFIG_FILE, {})
        cfg["theme"] = name
        save_json(CONFIG_FILE, cfg)
        current = self.root.current
        self.root.clear_widgets()
        for n, cls in [("splash",SplashScreen),("home",HomeScreen),("brain",BrainScreen),("bot",BotScreen),("settings",SettingsScreen),("info",InfoScreen)]:
            screen = cls(name=n)
            self.root.add_widget(screen)
            screen.build_bg()
        self.root.current = current

if __name__ == "__main__":
    ElmaBotApp().run()
