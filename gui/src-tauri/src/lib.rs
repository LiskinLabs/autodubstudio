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

            let mut started = false;

            if let Ok(home) = std::env::var("USERPROFILE") {
                let desktop_project = std::path::PathBuf::from(home).join("Desktop").join("AutoDubStudio");
                let desktop_venv_python = desktop_project.join(".venv").join("Scripts").join("python.exe");

                let desktop_venv_uvicorn = desktop_project.join(".venv").join("Scripts").join("uvicorn.exe");

                if desktop_venv_uvicorn.exists() {
                    let mut cmd = StdCommand::new(&desktop_venv_uvicorn);
                    cmd.args(["backend.main:app", "--host", "127.0.0.1", "--port", "8000"])
                       .current_dir(&desktop_project)
                       .stdout(Stdio::null())
                       .stderr(Stdio::null());

                    #[cfg(target_os = "windows")]
                    cmd.creation_flags(CREATE_NO_WINDOW);

                    if let Ok(child) = cmd.spawn() {
                        println!("[AutoDub] Backend started using Desktop .venv (PID: {})", child.id());
                        started = true;
                    }
                }
            }

            if !started {
                let resource_dir = app.path().resource_dir().unwrap_or_else(|_| std::env::current_dir().unwrap());
                let backend_candidates = vec![
                    resource_dir.join("backend").join("main.py"),
                    resource_dir.join("_up_").join("_up_").join("backend").join("main.py"),
                    resource_dir.join("_up_").join("backend").join("main.py"),
                    std::env::current_dir().unwrap().join("backend").join("main.py"),
                ];

                let backend_script = backend_candidates.iter().find(|p| p.exists());
                if let Some(script_path) = backend_script {
                    let project_dir = script_path.parent().unwrap().parent().unwrap();
                    let starters = vec![
                        ("uv", vec!["run", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                        ("python", vec!["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                    ];

                    for (prog, args) in &starters {
                        let mut cmd = StdCommand::new(prog);
                        cmd.args(args)
                           .current_dir(project_dir)
                           .stdout(Stdio::null())
                           .stderr(Stdio::null());
                        
                        #[cfg(target_os = "windows")]
                        cmd.creation_flags(CREATE_NO_WINDOW);

                        if let Ok(child) = cmd.spawn() {
                            println!("[AutoDub] Backend started: {} (PID: {})", prog, child.id());
                            started = true;
                            break;
                        }
                    }
                }
            }

            if !started {
                eprintln!("[AutoDub] WARNING: Could not start Python backend.");
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
