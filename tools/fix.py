import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'def build_stylesheet\(\):.*?return f.*?\"\"\"(.*?)\"\"\"'

replacement = '''def build_stylesheet():
    s = get_scheme()
    return f\"\"\"
    MainWindow, StackedWidget {{
        background-color: {s['surface']};
    }}
    QWidget#HomeInterface, QWidget#LiveInterface, QWidget#SettingsInterface, QWidget#AboutInterface {{
        background-color: {s['surface']};
    }}
    CardWidget, SimpleCardWidget {{
        background-color: {s['surface2']};
        border: 1px solid rgba({s['accent_rgb']}, 0.12);
        border-radius: 14px;
    }}
    CardWidget:hover, SimpleCardWidget:hover {{
        border: 1px solid rgba({s['accent_rgb']}, 0.35);
    }}
    \"\"\"'''

text = re.sub(pattern, replacement, text, flags=re.DOTALL)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
