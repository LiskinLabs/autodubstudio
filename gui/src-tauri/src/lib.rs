use std::process::{Command as StdCommand, Stdio};
use tauri::Manager;
use tauri::window::{Effect, EffectState, EffectsBuilder};

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
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            // Windows 11 Mica / Windows 10 Acrylic effect
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

            // Find backend command
            let (backend_program, backend_args, backend_dir): (String, Vec<&str>, std::path::PathBuf) = {
                let desktop_project = std::path::PathBuf::from(
                    std::env::var("USERPROFILE").unwrap_or_default()
                ).join("Desktop").join("AutoDubStudio");

                let uvicorn_path = desktop_project.join(".venv").join("Scripts").join("uvicorn.exe");
                if uvicorn_path.exists() {
                    (uvicorn_path.to_string_lossy().to_string(),
                     vec!["backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
                     desktop_project)
                } else {
                    let resource_dir = app.path().resource_dir()
                        .unwrap_or_else(|_| std::env::current_dir().unwrap());
                    let candidates = vec![
                        resource_dir.join("backend").join("main.py"),
                        resource_dir.join("_up_").join("_up_").join("backend").join("main.py"),
                        resource_dir.join("_up_").join("backend").join("main.py"),
                        std::env::current_dir().unwrap().join("backend").join("main.py"),
                    ];
                    let script = candidates.iter().find(|p| p.exists())
                        .map(|p| p.to_string_lossy().to_string())
                        .unwrap_or_default();
                    let dir = candidates.iter().find(|p| p.exists())
                        .and_then(|p| p.parent().and_then(|pp| pp.parent()))
                        .map(|d| d.to_path_buf())
                        .unwrap_or_else(|| std::env::current_dir().unwrap());
                    if script.is_empty() {
                        eprintln!("[AutoDub] Backend script not found!");
                        return Ok(());
                    }
                    ("uv".to_string(),
                     vec!["run", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
                     dir)
                }
            };

            // Auto-restart backend on crash
            std::thread::spawn(move || {
                let mut restart_count = 0u32;
                loop {
                    if restart_count > 0 {
                        println!("[AutoDub] Backend crashed — restarting in 2s (attempt {})...", restart_count);
                        std::thread::sleep(std::time::Duration::from_secs(2));
                    }

                    let log_file = backend_dir.join("autodub_backend.log");
                    // Rotate if > 5MB
                    if let Ok(meta) = std::fs::metadata(&log_file) {
                        if meta.len() > 5_000_000 {
                            let _ = std::fs::rename(&log_file, backend_dir.join("autodub_backend.old.log"));
                        }
                    }
                    let log_fd = std::fs::OpenOptions::new()
                        .create(true).append(true).open(&log_file)
                        .ok();

                    let mut cmd = StdCommand::new(&backend_program);
                    cmd.args(&backend_args)
                       .current_dir(&backend_dir);
                    if let Some(f) = log_fd {
                        let f2 = f.try_clone().unwrap();
                        cmd.stdout(Stdio::from(f)).stderr(Stdio::from(f2));
                    }

                    // Pass GitHub token from config.json for crash reporting
                    // In production, place config.json next to the .exe or in the project dir
                    for config_dir in &[backend_dir.clone(), std::env::current_dir().unwrap_or_default()] {
                        let config_path = config_dir.join("config.json");
                        if let Ok(config_str) = std::fs::read_to_string(&config_path) {
                            if let Ok(config) = serde_json::from_str::<serde_json::Value>(&config_str) {
                                if let Some(token) = config.get("github_token").and_then(|v| v.as_str()) {
                                    cmd.env("GITHUB_TOKEN", token);
                                    break;
                                }
                            }
                        }
                    }

                    #[cfg(target_os = "windows")]
                    cmd.creation_flags(CREATE_NO_WINDOW);

                    match cmd.spawn() {
                        Ok(mut child) => {
                            println!("[AutoDub] Backend started (PID: {}, restarts: {})", child.id(), restart_count);
                            let _ = child.wait();
                            // Child process died — write crash marker
                            if let Ok(mut f) = std::fs::File::create(
                                backend_dir.join("_backend_crashed.flag")
                            ) {
                                use std::io::Write;
                                let _ = writeln!(f, "backend_crashed");
                            }
                        }
                        Err(e) => {
                            eprintln!("[AutoDub] Failed to start backend: {}", e);
                            std::thread::sleep(std::time::Duration::from_secs(5));
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
