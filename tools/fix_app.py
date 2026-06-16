import io

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The corrupted lines start at 1039 (0-indexed, line 1040)
# And end right before the AboutInterface section, around 1243.
# Let's find exactly where to cut.
start_cut = -1
for i, line in enumerate(lines):
    if "def dk_changed" in line:
        start_cut = i + 1
        break

end_cut = -1
for i in range(start_cut, len(lines)):
    if "ABOUT INTERFACE" in lines[i]:
        # Backtrack to the comment line
        end_cut = i - 1
        break

if start_cut != -1 and end_cut != -1:
    new_lines = lines[:start_cut]
    new_lines.append('    def hk_changed(self, text): self.window().hf_key = text\n')
    new_lines.append('    def ui_lang_changed(self, text):\n')
    new_lines.append('        global current_lang\n')
    new_lines.append('        current_lang = text\n')
    new_lines.append('        show_info(self.window(), "Язык", "Перезапустите приложение для применения.")\n')
    new_lines.append('    def theme_changed(self, text):\n')
    new_lines.append('        if text == "Dark": setTheme(Theme.DARK)\n')
    new_lines.append('        elif text == "Light": setTheme(Theme.LIGHT)\n')
    new_lines.append('        else: setTheme(Theme.AUTO)\n')
    new_lines.append('    def scheme_changed(self, text):\n')
    new_lines.append('        global current_scheme_name\n')
    new_lines.append('        current_scheme_name = text\n')
    new_lines.append('        mw = self.window()\n')
    new_lines.append('        mw.setStyleSheet(build_stylesheet())\n')
    new_lines.append('        setThemeColor(QColor(get_scheme()[\'accent\']))\n')
    new_lines.append('        show_info(mw, "Тема", f"Цветовая схема: {text}")\n\n')
    new_lines.extend(lines[end_cut:])
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Fixed successfully!")
else:
    print(f"Could not find cut points: start={start_cut}, end={end_cut}")
