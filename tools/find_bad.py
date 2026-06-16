import re
with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

strings = re.findall(r'([\"\'])(.*?)\1', text)
bad_strings = set()
for _, s in strings:
    if re.search(r'[^\x00-\x7F]', s):
        bad_strings.add(s)

for s in bad_strings:
    print(s.encode('unicode_escape').decode())
