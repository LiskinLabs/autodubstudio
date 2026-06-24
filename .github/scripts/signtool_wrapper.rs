use std::process::Command;
use std::env;
use std::thread;
use std::time::Duration;

fn main() {
    let args: Vec<String> = env::args().collect();
    let real_signtool = "C:\\Program Files (x86)\\Windows Kits\\10\\bin\\10.0.22621.0\\x86\\signtool.exe";
    let mut success = false;
    for i in 1..=15 {
        println!("Signing attempt {}...", i);
        let status = Command::new(real_signtool)
            .args(&args[1..])
            .status()
            .expect("Failed to execute signtool");
        if status.success() {
            success = true;
            break;
        }
        thread::sleep(Duration::from_secs(30));
    }
    if !success {
        std::process::exit(1);
    }
}
