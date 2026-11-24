#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::Value;
use tauri::{
    menu::{MenuBuilder, SubmenuBuilder},
    webview::NewWindowResponse,
    AppHandle, Manager, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent,
};

#[cfg(target_os = "macos")]
mod macos;

trait HardwareCollector {
    fn collect(ticket: &str) -> Result<Value, String>;
}

#[cfg(not(target_os = "macos"))]
struct WindowsCollector;

#[cfg(not(target_os = "macos"))]
impl HardwareCollector for WindowsCollector {
    #[cfg(windows)]
    fn collect(ticket: &str) -> Result<Value, String> {
        use base64::engine::general_purpose::STANDARD;
        use base64::Engine;
        use std::io::Write;
        use std::os::windows::process::CommandExt;
        use std::path::PathBuf;
        use std::process::{Command, Stdio};
        use std::thread;
        use std::time::{Duration, Instant};

        if ticket.len() > 4096 {
            return Err("The scan ticket is too large.".into());
        }

        let script = include_str!("../../../web/public/collect-windows.ps1");
        let command = format!(
            "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); & {{\n{script}\n}} -TicketJson ([Console]::In.ReadToEnd())"
        );
        let encoded = STANDARD.encode(
            command
                .encode_utf16()
                .flat_map(u16::to_le_bytes)
                .collect::<Vec<_>>(),
        );
        let system = std::env::var_os("SystemRoot")
            .map(PathBuf::from)
            .ok_or("Windows SystemRoot is unavailable.")?;
        let mut child = Command::new(system.join("System32/WindowsPowerShell/v1.0/powershell.exe"))
            .args(["-NoProfile", "-NonInteractive", "-EncodedCommand", &encoded])
            .creation_flags(0x08000000)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|_| "Could not start the Windows collector.")?;

        let mut input = child.stdin.take().expect("piped stdin");
        if input.write_all(ticket.as_bytes()).is_err() {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Could not read the ticket in the Windows collector.".into());
        }
        drop(input);

        // Read concurrently so an unusually large CIM result cannot fill the child's pipe.
        let mut output = child.stdout.take().expect("piped stdout");
        let reader = thread::spawn(move || {
            use std::io::Read;
            let mut bytes = Vec::new();
            output.by_ref().take(65_537).read_to_end(&mut bytes)?;
            Ok::<_, std::io::Error>(bytes)
        });
        let deadline = Instant::now() + Duration::from_secs(45);
        loop {
            match child.try_wait() {
                Ok(Some(status)) if status.success() => break,
                Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(50)),
                result => {
                    let _ = child.kill();
                    let _ = child.wait();
                    let _ = reader.join();
                    return Err(if matches!(result, Ok(None)) {
                        "Hardware scan timed out. Try a fresh ticket."
                    } else {
                        "The scan failed. Check that the ticket is current and Windows hardware information is available."
                    }.into());
                }
            }
        }

        let bytes = reader
            .join()
            .ok()
            .and_then(Result::ok)
            .ok_or("Could not read the scan output.")?;
        parse_output(&bytes)
    }

    #[cfg(not(windows))]
    fn collect(_: &str) -> Result<Value, String> {
        Err("The Windows hardware collector is unavailable on this platform.".into())
    }
}

#[cfg(any(windows, test))]
fn parse_output(bytes: &[u8]) -> Result<Value, String> {
    if bytes.len() > 65_536 {
        return Err("The scan output exceeded the size limit.".into());
    }
    let result: Value =
        serde_json::from_slice(bytes).map_err(|_| "The collector returned invalid data.")?;
    if result.get("platform").and_then(Value::as_str) != Some("windows")
        || !result.get("hardware").is_some_and(Value::is_object)
    {
        return Err("The collector did not return Windows hardware data.".into());
    }
    Ok(result)
}

fn is_local_scanner(window: &WebviewWindow) -> bool {
    if window.label() != "main" {
        return false;
    }
    window.url().is_ok_and(|url| {
        matches!(
            (url.scheme(), url.host_str(), url.port()),
            ("tauri", Some("localhost"), None) | ("http" | "https", Some("tauri.localhost"), None)
        ) || (cfg!(debug_assertions)
            && url.scheme() == "http"
            && url.host_str() == Some("127.0.0.1")
            && url.port() == Some(1420))
    })
}

fn workspace_origin() -> Option<Url> {
    let configured = option_env!("PROOFSCAN_WEB_ORIGIN")
        .filter(|value| !value.is_empty())
        .or_else(|| cfg!(debug_assertions).then_some("http://localhost:3000"))?;
    let url = Url::parse(configured).ok()?;
    let local_dev = cfg!(debug_assertions)
        && url.scheme() == "http"
        && matches!(url.host_str(), Some("localhost" | "127.0.0.1"));
    if (url.scheme() != "https" && !local_dev)
        || !url.has_host()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.path() != "/"
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return None;
    }
    Some(url)
}

fn workspace_window(app: &AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("workspace") {
        return window.set_focus().map_err(|err| err.to_string());
    }
    let mut url = workspace_origin()
        .ok_or("Set the ProofScan workspace origin before building the desktop app.")?;
    let origin = url.origin();
    url.set_path("/workspace");
    WebviewWindowBuilder::new(app, "workspace", WebviewUrl::External(url))
        .title("ProofScan")
        .inner_size(1200.0, 820.0)
        .min_inner_size(360.0, 520.0)
        .on_navigation(move |next| {
            next.origin() == origin && next.username().is_empty() && next.password().is_none()
        })
        .on_new_window(|_, _| NewWindowResponse::Deny)
        .build()
        .map(|_| ())
        .map_err(|err| err.to_string())
}

#[tauri::command]
async fn show_workspace(window: WebviewWindow, app: AppHandle) -> Result<(), String> {
    if !is_local_scanner(&window) {
        return Err("Open the workspace from the ProofScan scanner.".into());
    }
    workspace_window(&app)
}

#[tauri::command]
async fn collect_hardware(window: WebviewWindow, ticket: String) -> Result<Value, String> {
    if !is_local_scanner(&window) {
        return Err("Hardware is available in the local device scanner.".into());
    }
    #[cfg(target_os = "macos")]
    let collect = macos::MacCollector::collect;
    #[cfg(not(target_os = "macos"))]
    let collect = WindowsCollector::collect;
    tauri::async_runtime::spawn_blocking(move || collect(&ticket))
        .await
        .map_err(|_| "The collector stopped unexpectedly.".to_owned())?
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![collect_hardware, show_workspace])
        .setup(|app| {
            let tools = SubmenuBuilder::new(app, "ProofScan")
                .text("workspace", "Workspace")
                .text("scanner", "Device scanner")
                .build()?;
            app.set_menu(MenuBuilder::new(app).item(&tools).build()?)?;
            if workspace_window(app.handle()).is_ok() {
                if let Some(scanner) = app.get_webview_window("main") {
                    let _ = scanner.hide();
                }
            }
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().0.as_str() {
            "workspace" => {
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let _ = workspace_window(&app);
                });
            }
            "scanner" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            _ => {}
        })
        .on_window_event(|window, event| {
            if window.label() == "workspace" && matches!(event, WindowEvent::Destroyed) {
                if let Some(scanner) = window.app_handle().get_webview_window("main") {
                    let _ = scanner.show();
                    let _ = scanner.set_focus();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("Could not start ProofScan");
}

#[cfg(test)]
mod tests {
    use super::parse_output;

    #[test]
    fn accepts_windows_evidence() {
        let result =
            parse_output(br#"{"platform":"windows","hardware":{"memory_gib":16}}"#).unwrap();
        assert_eq!(result["hardware"]["memory_gib"], 16);
    }

    #[test]
    fn rejects_non_windows_and_oversize_output() {
        assert!(parse_output(br#"{"platform":"simulator","hardware":{}}"#).is_err());
        assert!(parse_output(&vec![0; 65_537]).is_err());
    }
}
