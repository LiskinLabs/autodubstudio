use std::process::{Command as StdCommand, Stdio};
use std::sync::Mutex;
use tauri::Manager;
use tauri::window::{Effect, EffectState, EffectsBuilder};

struct BackendProcess(Mutex<Option<std::process::Child>>);

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
        .manage(BackendProcess(Mutex::new(None)))
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
                let script_dir = script_path.parent().unwrap();
                let project_dir = script_dir.parent().unwrap();

                // Try uv run first (fast, uses .venv), then system python, then python3
                let python_cmds = vec![
                    ("uv", vec!["run", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                    ("python", vec!["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                ];

                let state = app.state::<BackendProcess>();

                for (cmd, args) in &python_cmds {
                    let child = StdCommand::new(cmd)
                        .args(args)
                        .current_dir(project_dir)
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn();

                    if let Ok(child) = child {
                        println!("[AutoDub] Backend started with: {} (PID: {})", cmd, child.id());
                        *state.0.lock().unwrap() = Some(child);
                        break;
                    }
                }

                if state.0.lock().unwrap().is_none() {
                    // Last resort: try the .venv python
                    let venv_python = project_dir.join(".venv").join("Scripts").join("python.exe");
                    if venv_python.exists() {
                        let child = StdCommand::new(venv_python)
                            .arg(script_path)
                            .stdout(Stdio::null())
                            .stderr(Stdio::null())
                            .spawn();
                        if let Ok(child) = child {
                            println!("[AutoDub] Backend started with .venv python (PID: {})", child.id());
                            *state.0.lock().unwrap() = Some(child);
                        }
                    }
                }

                if state.0.lock().unwrap().is_none() {
                    eprintln!("[AutoDub] Could not start backend. Python/uv not found.");
                }
            } else {
                eprintln!("[AutoDub] Backend script not found at any expected location.");
            }

            Ok(())
        })
        .on_event(|app, event| {
            if let tauri::RunEvent::Exit = event {
                // Kill the backend process on app exit
                if let Some(state) = app.try_state::<BackendProcess>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        println!("[AutoDub] Backend process stopped.");
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
