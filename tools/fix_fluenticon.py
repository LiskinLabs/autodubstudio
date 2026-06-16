
import re
with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('icon: FluentIcon', 'icon: FIF')
text = text.replace('FluentIcon.', 'FIF.')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)

