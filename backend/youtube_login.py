import webview
import time
import os
import threading

def save_cookies(window):
    while True:
        try:
            time.sleep(2)
            cookies = window.get_cookies()
            if cookies:
                cookie_file = os.path.join(os.path.dirname(__file__), "youtube_cookies.txt")
                with open(cookie_file, "w", encoding="utf-8") as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                    f.write("# This is a generated file!  Do not edit.\n\n")
                    for cookie_dict in cookies:
                        for key, morsel in cookie_dict.items():
                            domain = morsel.get("domain", ".youtube.com")
                            if not domain: domain = ".youtube.com"
                            path = morsel.get("path", "/")
                            if not path: path = "/"
                            secure = "TRUE" if morsel.get("secure", True) else "FALSE"
                            initial_dot = "TRUE" if domain.startswith(".") else "FALSE"
                            f.write(f"{domain}\t{initial_dot}\t{path}\t{secure}\t0\t{key}\t{morsel.value}\n")
        except Exception as e:
            # Window probably closed
            break

if __name__ == '__main__':
    window = webview.create_window(
        'Авторизация YouTube (AutoDubStudio)', 
        'https://accounts.google.com/ServiceLogin?service=youtube&passive=true&continue=https://www.youtube.com/&hl=ru',
        width=800,
        height=600
    )

    def start_save():
        t = threading.Thread(target=save_cookies, args=(window,), daemon=True)
        t.start()

    webview.start(start_save, private_mode=False)
