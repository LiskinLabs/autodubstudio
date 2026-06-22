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

/// Tauri command: kill all Python processes, clear caches, backend auto-restarts
#[tauri::command]
fn restart_backend() -> String {
    // 1. Kill all python.exe processes
    #[cfg(target_os = "windows")]
    {
        let _ = StdCommand::new("cmd")
            .args(["/c", "taskkill /F /IM python.exe 2>nul"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = StdCommand::new("sh")
            .args(["-c", "pkill -9 python 2>/dev/null; pkill -9 python3 2>/dev/null; true"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }

    // 2. Clear Python bytecode cache
    let proj_dir = std::path::PathBuf::from(
        std::env::var("USERPROFILE").unwrap_or_default()
    ).join("Desktop").join("AutoDubStudio");

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
    clear_pycache(&proj_dir);

    // Also clear AppData caches
    if let Ok(appdata) = std::env::var("LOCALAPPDATA") {
        let ad = std::path::PathBuf::from(appdata).join("AutoDub Studio");
        clear_pycache(&ad);
    }

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
        .invoke_handler(tauri::generate_handler![restart_backend])
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
                // ── Check if backend is already running ──
                if is_backend_alive() {
                    println!("[AutoDub] Backend already running on port 8000 — monitoring");
                    // Just monitor: keep checking if it's alive
                    loop {
                        std::thread::sleep(Duration::from_secs(10));
                        if !is_backend_alive() {
                            println!("[AutoDub] Backend died — will restart");
                            break;
                        }
                    }
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

                    let python_exe = backend_dir.join(".venv").join("Scripts").join("python.exe");
                    let python_exe_local = uv_env_dir.join("Scripts").join("python.exe");

                    let (program, args): (String, Vec<String>) = if python_exe.exists() {
                        (python_exe.to_string_lossy().to_string(),
                         vec!["backend/main.py".to_string()])
                    } else if python_exe_local.exists() {
                        (python_exe_local.to_string_lossy().to_string(),
                         vec!["backend/main.py".to_string()])
                    } else {
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
                            println!("[AutoDub] uv not found, installing it...");
                            #[cfg(target_os = "windows")]
                            let _ = StdCommand::new("powershell")
                                .args(["-ExecutionPolicy", "ByPass", "-c", "irm https://astral.sh/uv/install.ps1 | iex"])
                                .creation_flags(CREATE_NO_WINDOW)
                                .status();
                            uv_path.to_string_lossy().to_string()
                        };

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

                    // Pass GitHub token
                    let config_path = backend_dir.join("config.json");
                    if let Ok(config_str) = std::fs::read_to_string(&config_path) {
                        if let Ok(config) = serde_json::from_str::<serde_json::Value>(&config_str) {
                            if let Some(token) = config.get("github_token").and_then(|v| v.as_str()) {
                                cmd.env("GITHUB_TOKEN", token);
                            }
                        }
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
