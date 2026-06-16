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
            let resource_dir = app.path().resource_dir()
                .unwrap_or_else(|_| std::env::current_dir().unwrap());

            // Try multiple possible backend locations (dev vs installed)
            let backend_candidates = vec![
                resource_dir.join("backend").join("main.py"),
                resource_dir.join("_up_").join("_up_").join("backend").join("main.py"),
                resource_dir.join("_up_").join("backend").join("main.py"),
                std::env::current_dir().unwrap().join("backend").join("main.py"),
            ];

            let backend_script = backend_candidates.iter().find(|p| p.exists());

            if let Some(script_path) = backend_script {
                let project_dir = script_path.parent().unwrap().parent().unwrap();

                // Try python/uv to start uvicorn backend
                let starters = vec![
                    ("uv", vec!["run", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                    ("python", vec!["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                ];

                let mut started = false;
                for (cmd, args) in &starters {
                    if let Ok(child) = StdCommand::new(cmd)
                        .args(args)
                        .current_dir(project_dir)
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn()
                    {
                        println!("[AutoDub] Backend started: {} (PID: {})", cmd, child.id());
                        started = true;
                        break;
                    }
                }

                // Fallback: .venv python (check project_dir + well-known dev location)
                if !started {
                    let mut venv_dirs = vec![
                        project_dir.join(".venv"),
                    ];
                    // Desktop project — user-controlled dev environment
                    if let Ok(home) = std::env::var("USERPROFILE") {
                        venv_dirs.push(std::path::PathBuf::from(home)
                            .join("Desktop").join("AutoDubStudio").join(".venv"));
                    }

                    for venv_dir in &venv_dirs {
                        let venv_python = venv_dir.join("Scripts").join("python.exe");
                        if venv_python.exists() {
                            if let Ok(child) = StdCommand::new(&venv_python)
                                .arg(script_path)
                                .stdout(Stdio::null())
                                .stderr(Stdio::null())
                                .spawn()
                            {
                                println!("[AutoDub] Backend started: {} (PID: {})", venv_python.display(), child.id());
                                started = true;
                                break;
                            }
                        }
                    }
                }

                if !started {
                    eprintln!("[AutoDub] WARNING: Could not start Python backend. Is Python/uv installed?");
                    eprintln!("[AutoDub] The app needs a running backend at http://127.0.0.1:8000");
                }
            } else {
                eprintln!("[AutoDub] Backend script not found. Looked in:");
                for c in &backend_candidates {
                    eprintln!("  - {}", c.display());
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
