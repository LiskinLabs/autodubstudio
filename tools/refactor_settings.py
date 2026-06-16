import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add necessary qfluentwidgets imports
import_qfw = '''from qfluentwidgets import (
    FluentWindow, SubtitleLabel, setFont, ComboBox, PushButton,
    LineEdit, PasswordLineEdit, CheckBox, TextEdit, ProgressBar,
    Theme, setTheme, qconfig, setThemeColor, SmoothScrollArea,
    SettingCardGroup, PrimaryPushSettingCard, OptionsSettingCard,
    ComboBoxSettingCard, SwitchSettingCard, CustomColorSettingCard,
    PasswordSettingCard, HyperlinkCard, FluentIcon as FIF, ScrollArea,
    ExpandLayout
)'''
text = re.sub(r'from qfluentwidgets import \([^)]+\)', import_qfw, text)

# Delete oklch imports and references
text = re.sub(r'from oklch_theme import.*?\n', '', text)
text = re.sub(r'COLOR_SCHEMES = .*?\n', '', text)
text = re.sub(r'current_scheme_name = .*?\n', '', text)

# Rewrite SettingsInterface
settings_class_pattern = r'class SettingsInterface\(QWidget\):.*?class AboutInterface'
settings_replacement = '''class SettingsInterface(ScrollArea):
    check_api_signal = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("SettingsInterface")
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea{border: none; background: transparent;}")
        self.scrollWidget.setStyleSheet("QWidget{background: transparent;}")

        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.setSpacing(28)

        # 1. API Keys Group
        self.apiGroup = SettingCardGroup("API Keys (Integrations)", self.scrollWidget)
        
        # Gemini
        self.geminiCard = PasswordSettingCard(
            FIF.FINGERPRINT, "Gemini API Key", "Get key from aistudio.google.com", self.apiGroup
        )
        self.geminiCard.lineEdit.setPlaceholderText("AIzaSy...")
        self.geminiCard.lineEdit.textChanged.connect(self.gk_changed)
        self.geminiVerifyBtn = PushButton("Verify")
        self.geminiVerifyBtn.clicked.connect(lambda: self.verify_api("Gemini", self.geminiCard.lineEdit.text()))
        self.geminiCard.hBoxLayout.addWidget(self.geminiVerifyBtn, 0, Qt.AlignmentFlag.AlignRight)
        self.apiGroup.addSettingCard(self.geminiCard)

        # DeepSeek
        self.deepseekCard = PasswordSettingCard(
            FIF.FINGERPRINT, "DeepSeek API Key", "Get key from platform.deepseek.com", self.apiGroup
        )
        self.deepseekCard.lineEdit.setPlaceholderText("sk-...")
        self.deepseekCard.lineEdit.textChanged.connect(self.dk_changed)
        self.dsVerifyBtn = PushButton("Verify")
        self.dsVerifyBtn.clicked.connect(lambda: self.verify_api("DeepSeek", self.deepseekCard.lineEdit.text()))
        self.deepseekCard.hBoxLayout.addWidget(self.dsVerifyBtn, 0, Qt.AlignmentFlag.AlignRight)
        self.apiGroup.addSettingCard(self.deepseekCard)

        # HuggingFace
        self.hfCard = PasswordSettingCard(
            FIF.FINGERPRINT, "HuggingFace Token", "Required for Pyannote Diarization", self.apiGroup
        )
        self.hfCard.lineEdit.setPlaceholderText("hf_...")
        self.hfCard.lineEdit.setText("hf_...")  # Set your HuggingFace token here
        self.hfCard.lineEdit.textChanged.connect(self.hk_changed)
        self.hfVerifyBtn = PushButton("Verify")
        self.hfVerifyBtn.clicked.connect(lambda: self.verify_api("HuggingFace", self.hfCard.lineEdit.text()))
        self.hfCard.hBoxLayout.addWidget(self.hfVerifyBtn, 0, Qt.AlignmentFlag.AlignRight)
        self.apiGroup.addSettingCard(self.hfCard)

        self.expandLayout.addWidget(self.apiGroup)

        # 2. UI Group
        self.uiGroup = SettingCardGroup("User Interface", self.scrollWidget)

        self.themeCard = ComboBoxSettingCard(
            qconfig.themeMode,
            FIF.BRUSH,
            "Application Theme",
            "Select light, dark or system theme",
            texts=["Light", "Dark", "Auto"],
            parent=self.uiGroup
        )
        self.themeCard.comboBox.currentTextChanged.connect(self.theme_changed)
        self.uiGroup.addSettingCard(self.themeCard)

        self.expandLayout.addWidget(self.uiGroup)

    def verify_api(self, engine, key):
        if not key.strip():
            show_info(self.window(), "Error", "API key is empty!", is_error=True)
            return
        import threading
        threading.Thread(target=self._test_api_thread, args=(engine, key)).start()

    def _test_api_thread(self, engine, key):
        try:
            if engine == "Gemini":
                from google import genai
                client = genai.Client(api_key=key)
                client.models.generate_content(model="gemini-2.5-flash", contents="Test")
            elif engine == "DeepSeek":
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
                client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": "Test"}], max_tokens=10)
            elif engine == "HuggingFace":
                from pyannote.audio import Pipeline
                import torch
                try:
                    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=key)
                    if pipeline is None: raise Exception("Pipeline is None")
                except Exception as e:
                    raise Exception(f"Accept terms for models.\\n{e}")
            self.window().api_check_result_signal.emit(True, f"{engine} API is working!")
        except Exception as e:
            self.window().api_check_result_signal.emit(False, f"Error {engine}:\\n{e}")

    def gk_changed(self, text): self.window().gemini_key = text
    def dk_changed(self, text): self.window().deepseek_key = text
    def hk_changed(self, text): self.window().hf_key = text
    
    def theme_changed(self, text):
        if text == "Dark": setTheme(Theme.DARK)
        elif text == "Light": setTheme(Theme.LIGHT)
        else: setTheme(Theme.AUTO)

class AboutInterface'''

text = re.sub(settings_class_pattern, settings_replacement, text, flags=re.DOTALL)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("app.py settings refactored.")
