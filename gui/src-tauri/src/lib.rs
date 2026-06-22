use std::process::{Command as StdCommand, Stdio};
use std::net::TcpStream;
use std::time::Duration;
use tauri::Manager;
use tauri::window::{Effect, EffectState, EffectsBuilder};

/// Check if backend is already alive on port 8000
fn is_backend_alive() -> bool {
    TcpStream::connect_timeout(
        &"127.0.0.1:8000".parse().unwrap(),
        Duration::from_millis(500),
    ).is_ok()
}

/// Kill any process holding port 8000 (best-effort, Windows only)
#[cfg(target_os = "windows")]
fn kill_port_8000() {
    let _ = StdCommand::new("cmd")
        .args(["/c", "for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :8000.*LISTENING') do @taskkill /F /PID %a 2>nul"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(not(target_os = "windows"))]
fn kill_port_8000() {
    let _ = StdCommand::new("sh")
        .args(["-c", "lsof -ti:8000 | xargs kill -9 2>/dev/null; true"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

/// Tauri command: kill backend on port 8000, clear caches async, backend auto-restarts
/// Возвращает мгновенно — очистка кэша в фоне, UI не фризится
#[tauri::command]
fn restart_backend() -> String {
    // 1. Kill backend on port 8000 (fast, synchronous)
    kill_port_8000();
    std::thread::sleep(Duration::from_millis(300));

    // 2. Clear Python bytecode cache in BACKGROUND (non-blocking)
    std::thread::spawn(|| {
        fn clear_pycache(dir: &std::path::Path) {
            if let Ok(entries) = std::fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_dir() {
                        if path.file_name().map_or(false, |n| n == "__pycache__") {
                            let _ = std::fs::remove_dir_all(&path);
                            println!("[AutoDub] Cleared: {}", path.display());
                        } else {
                            clear_pycache(&path);
                        }
                    }
                }
            }
        }
        // Desktop project cache
        let proj_dir = std::path::PathBuf::from(
            std::env::var("USERPROFILE").unwrap_or_default()
        ).join("Desktop").join("AutoDubStudio");
        clear_pycache(&proj_dir);
        // AppData installed cache
        if let Ok(appdata) = std::env::var("LOCALAPPDATA") {
            let ad = std::path::PathBuf::from(appdata).join("AutoDub Studio");
            clear_pycache(&ad);
        }
    });

    "ok".to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            restart_backend,
            check_dependency,
            install_dependency,
            get_missing_deps,
        ])
        .setup(|app| {
            // ── Clean Python caches on startup ──
            #[cfg(target_os = "windows")]
            {
                let _ = StdCommand::new("cmd")
                    .args(["/c", "for /d /r \"%USERPROFILE%\\Desktop\\AutoDubStudio\" %d in (__pycache__) do @if exist \"%d\" rd /s /q \"%d\" 2>nul"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status();
            }
            let window = app.get_webview_window("main").unwrap();

            // Windows 11 Mica effect
            #[cfg(target_os = "windows")]
            {
                let effects = EffectsBuilder::new()
                    .effect(Effect::Mica)
                    .state(EffectState::Active)
                    .build();
                let _ = window.set_effects(effects);
            }

            // ── Auto-start Python Backend ──
            #[cfg(target_os = "windows")]
            use std::os::windows::process::CommandExt;
            #[cfg(target_os = "windows")]
            const CREATE_NO_WINDOW: u32 = 0x08000000;

            let backend_dir = {
                let desktop = std::path::PathBuf::from(
                    std::env::var("USERPROFILE").unwrap_or_default()
                ).join("Desktop").join("AutoDubStudio");
                if desktop.join("backend").join("main.py").exists() {
                    desktop
                } else {
                    app.path().resource_dir().unwrap_or_else(|_| std::env::current_dir().unwrap_or_default())
                }
            };

            std::thread::spawn(move || {
                // ── ВСЕГДА перезапускаем бекенд при старте приложения ──
                // Это гарантирует что пользователь всегда работает со свежим кодом
                // Старый процесс на порту 8000 убивается, даже если отвечает
                if is_backend_alive() {
                    println!("[AutoDub] Killing stale backend on port 8000...");
                    kill_port_8000();
                    std::thread::sleep(Duration::from_millis(500));
                }

                let mut restart_count = 0u32;
                const MAX_RESTARTS: u32 = 20;

                loop {
                    if restart_count >= MAX_RESTARTS {
                        eprintln!("[AutoDub] Backend crashed {} times — giving up", restart_count);
                        break;
                    }

                    if restart_count > 0 {
                        let delay_secs = (2u64.saturating_pow(restart_count)).min(60);
                        println!("[AutoDub] Restarting backend in {}s (attempt {}/{})", delay_secs, restart_count, MAX_RESTARTS);
                        std::thread::sleep(Duration::from_secs(delay_secs));

                        // Kill stale processes on port 8000 before restart
                        kill_port_8000();
                        std::thread::sleep(Duration::from_millis(500));
                    }

                    // Skip if already alive
                    if is_backend_alive() {
                        println!("[AutoDub] Backend already alive — waiting for it to exit");
                        loop {
                            std::thread::sleep(Duration::from_secs(10));
                            if !is_backend_alive() {
                                println!("[AutoDub] Backend exited — will restart");
                                restart_count += 1;
                                break;
                            }
                        }
                        continue;
                    }

                    let local_appdata = std::env::var("LOCALAPPDATA").unwrap_or_default();
                    let uv_env_dir = std::path::PathBuf::from(&local_appdata).join("AutoDub Studio").join(".venv");

                    // Приоритет поиска Python: .venv → другие venv → AppData .venv → uv run
                    // Поддерживаем множественные venv (основной .venv, .venv-f5, .venv-qwen3-tts и др.)
                    let python_exe = backend_dir.join(".venv").join("Scripts").join("python.exe");
                    let python_exe_local = uv_env_dir.join("Scripts").join("python.exe");

                    // Ищем любой доступный venv в папке проекта
                    let find_any_venv = || {
                        if let Ok(entries) = std::fs::read_dir(&backend_dir) {
                            for entry in entries.flatten() {
                                let name = entry.file_name();
                                let name_str = name.to_string_lossy();
                                if name_str.starts_with(".venv") {
                                    let py = entry.path().join("Scripts").join("python.exe");
                                    if py.exists() { return Some(py); }
                                }
                            }
                        }
                        None
                    };

                    let (program, args): (String, Vec<String>) = if python_exe.exists() {
                        (python_exe.to_string_lossy().to_string(),
                         vec!["backend/main.py".to_string()])
                    } else if let Some(any_venv) = find_any_venv() {
                        println!("[AutoDub] Using alternative venv: {}", any_venv.display());
                        (any_venv.to_string_lossy().to_string(),
                         vec!["backend/main.py".to_string()])
                    } else if python_exe_local.exists() {
                        (python_exe_local.to_string_lossy().to_string(),
                         vec!["backend/main.py".to_string()])
                    } else {
                        // Проверяем uv — если не установлен, ПРОПУСКАЕМ (без автоустановки)
                        #[cfg(target_os = "windows")]
                        let uv_check = StdCommand::new("uv").arg("--version").creation_flags(CREATE_NO_WINDOW).status();
                        #[cfg(not(target_os = "windows"))]
                        let uv_check = StdCommand::new("uv").arg("--version").status();

                        let uv_path = std::path::PathBuf::from(std::env::var("USERPROFILE").unwrap_or_default()).join(".cargo").join("bin").join("uv.exe");
                        let uv_cmd = if uv_check.is_ok() {
                            "uv".to_string()
                        } else if uv_path.exists() {
                            uv_path.to_string_lossy().to_string()
                        } else {
                            eprintln!("[AutoDub] uv not found. Please install uv manually: https://docs.astral.sh/uv/");
                            // Не устанавливаем uv без согласия пользователя — безопасность
                            std::thread::sleep(Duration::from_secs(30));
                            continue;
                        };

                        // uv run должен запускаться из КОРНЯ проекта (где pyproject.toml), не из backend/
                        (uv_cmd,
                         vec!["run".to_string(), "python".to_string(), "backend/main.py".to_string()])
                    };

                    // Log file
                    let log_file = backend_dir.join("autodub_backend.log");
                    if let Ok(meta) = std::fs::metadata(&log_file) {
                        if meta.len() > 5_000_000 {
                            let _ = std::fs::rename(&log_file, backend_dir.join("autodub_backend.old.log"));
                        }
                    }
                    let log_fd = std::fs::OpenOptions::new()
                        .create(true).append(true).open(&log_file).ok();

                    let mut cmd = StdCommand::new(&program);
                    cmd.args(&args).current_dir(&backend_dir);
                    cmd.env("UV_PROJECT_ENVIRONMENT", &uv_env_dir);

                    if let Some(f) = log_fd {
                        let f2 = f.try_clone().unwrap();
                        cmd.stdout(Stdio::from(f)).stderr(Stdio::from(f2));
                    }

                    // Pass GitHub token — приоритет: config.json → github_token.txt
                    let mut github_token = String::new();
                    // 1. config.json (пользователь может переопределить)
                    let config_path = backend_dir.join("config.json");
                    if let Ok(config_str) = std::fs::read_to_string(&config_path) {
                        if let Ok(config) = serde_json::from_str::<serde_json::Value>(&config_str) {
                            if let Some(t) = config.get("github_token").and_then(|v| v.as_str()) {
                                if !t.is_empty() {
                                    github_token = t.to_string();
                                }
                            }
                        }
                    }
                    // 2. Fallback: github_token.txt (вшит в инсталлятор, не в git)
                    if github_token.is_empty() {
                        let token_file = backend_dir.join("github_token.txt");
                        if let Ok(t) = std::fs::read_to_string(&token_file) {
                            let trimmed = t.trim();
                            if !trimmed.is_empty() {
                                github_token = trimmed.to_string();
                            }
                        }
                    }
                    if !github_token.is_empty() {
                        cmd.env("GITHUB_TOKEN", &github_token);
                    }

                    #[cfg(target_os = "windows")]
                    cmd.creation_flags(CREATE_NO_WINDOW);

                    match cmd.spawn() {
                        Ok(mut child) => {
                            println!("[AutoDub] Backend started (PID: {}, restarts: {})", child.id(), restart_count);
                            let status = child.wait();
                            println!("[AutoDub] Backend exited: {:?}", status);
                        }
                        Err(e) => {
                            eprintln!("[AutoDub] Failed to start backend: {}", e);
                            std::thread::sleep(Duration::from_secs(5));
                        }
                    }
                    restart_count += 1;
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// ═══════════════════════════════════════════════════════════════════════
// Dependency Checker & Auto-Installer — First-Run Wizard
// Проверяет и устанавливает Python, uv, Ollama, FFmpeg при первом запуске
// ═══════════════════════════════════════════════════════════════════════

/// Check if a command is available on PATH
fn check_command(cmd: &str, args: &[&str]) -> bool {
    StdCommand::new(cmd)
        .args(args)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Check status of all required dependencies
#[tauri::command]
fn check_dependency(name: String) -> serde_json::Value {
    let (installed, version) = match name.as_str() {
        "python" => {
            let ok = check_command("python", &["--version"])
                || check_command("python3", &["--version"]);
            let ver = if ok {
                StdCommand::new("python")
                    .arg("--version")
                    .output()
                    .ok()
                    .and_then(|o| String::from_utf8(o.stdout).ok())
                    .unwrap_or_default()
                    .trim()
                    .to_string()
            } else {
                String::new()
            };
            (ok, ver)
        }
        "uv" => {
            let ok = check_command("uv", &["--version"]);
            (ok, String::new())
        }
        "ollama" => {
            let ok = check_command("ollama", &["--version"]);
            (ok, String::new())
        }
        "ffmpeg" => {
            let ok = check_command("ffmpeg", &["-version"]);
            (ok, String::new())
        }
        _ => (false, String::new()),
    };
    serde_json::json!({
        "name": name,
        "installed": installed,
        "version": version,
    })
}

/// Install a dependency using winget (Windows 11 built-in) or manual download URL
/// Возвращает URL для ручной установки если winget недоступен
#[tauri::command]
fn install_dependency(name: String) -> serde_json::Value {
    let winget_ok = check_command("winget", &["--version"]);

    // Пробуем установить через winget (тихо, с согласия пользователя)
    if winget_ok {
        let package = match name.as_str() {
            "python" => "Python.Python.3.12",
            "uv" => "astral-sh.uv",
            "ollama" => "Ollama.Ollama",
            "ffmpeg" => "Gyan.FFmpeg",
            _ => return serde_json::json!({"status": "error", "message": "Unknown package"}),
        };

        let result = StdCommand::new("winget")
            .args(["install", "--id", package, "--accept-source-agreements", "--accept-package-agreements", "--silent"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();

        if result.map(|s| s.success()).unwrap_or(false) {
            return serde_json::json!({"status": "installed", "name": name});
        }
    }

    // Fallback: даём ссылку для ручной установки
    let manual_url = match name.as_str() {
        "python" => "https://www.python.org/downloads/",
        "uv" => "https://docs.astral.sh/uv/getting-started/installation/",
        "ollama" => "https://ollama.com/download/windows",
        "ffmpeg" => "https://www.gyan.dev/ffmpeg/builds/",
        _ => "",
    };
    serde_json::json!({
        "status": "manual",
        "name": name,
        "url": manual_url,
        "message": "Please install manually — winget not available or install failed",
    })
}

/// Get list of all missing dependencies
#[tauri::command]
fn get_missing_deps() -> serde_json::Value {
    let deps = vec![
        ("python", "Python 3.12+", "Required to run the AI backend", "https://www.python.org/downloads/"),
        ("uv", "uv (Python package manager)", "Fast Python dependency management", "https://docs.astral.sh/uv/getting-started/installation/"),
        ("ollama", "Ollama", "Local AI models for translation & chat", "https://ollama.com/download/windows"),
        ("ffmpeg", "FFmpeg", "Video/audio processing & muxing", "https://www.gyan.dev/ffmpeg/builds/"),
    ];

    let mut missing = Vec::new();
    for (id, _label, _desc, url) in &deps {
        if !check_command(id, &["--version"]) && !check_command(id, &["-version"]) {
            // Special check for python: try python3 too
            if *id == "python" {
                if !check_command("python3", &["--version"]) {
                    missing.push(serde_json::json!({
                        "id": id, "label": _label, "description": _desc, "url": url,
                    }));
                }
            } else {
                missing.push(serde_json::json!({
                    "id": id, "label": _label, "description": _desc, "url": url,
                }));
            }
        }
    }
    serde_json::json!({ "missing": missing })
}
