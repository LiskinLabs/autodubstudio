import re
with open(r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\backend\translator.py", "r", encoding="utf-8") as f:
    text = f.read()

# The regex will match the broken f-string which has physical newlines:
# f"[{j}] {spk} (Duration: ... chars)
#     Original: {orig}
#     Draft: {base}"
pattern1 = re.compile(r'f"\[\{j\}\] \{spk\} \(Duration: \{duration:\.1f\}s, Max length: \{max_chars\} chars\)\n\s+Original: \{orig\}\n\s+Draft: \{base\}"')
text = pattern1.sub(r'f"[{j}] {spk} (Duration: {duration:.1f}s, Max length: {max_chars} chars)\\n    Original: {orig}\\n    Draft: {base}"', text)

pattern2 = re.compile(r'f"\[\{i\}\] \{spk\} \(Duration: \{duration:\.1f\}s, Max length: \{max_chars\} chars\)\n\s+Original: \{orig\}\n\s+Draft: \{base\}"')
text = pattern2.sub(r'f"[{i}] {spk} (Duration: {duration:.1f}s, Max length: {max_chars} chars)\\n    Original: {orig}\\n    Draft: {base}"', text)

with open(r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\backend\translator.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Done")
