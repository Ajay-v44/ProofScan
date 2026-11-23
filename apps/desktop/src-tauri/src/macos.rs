use serde_json::{json, Value};
use std::process::Command;

use crate::HardwareCollector;

pub(crate) struct MacCollector;

fn sysctl(name: &str) -> Option<String> {
    let result = Command::new("/usr/sbin/sysctl")
        .args(["-n", name])
        .output()
        .ok()?;
    if !result.status.success() {
        return None;
    }
    let value = String::from_utf8(result.stdout).ok()?;
    let label: String = value.trim().chars().take(120).collect();
    (!label.is_empty()).then_some(label)
}

impl HardwareCollector for MacCollector {
    fn collect(ticket: &str) -> Result<Value, String> {
        if ticket.len() > 4096 {
            return Err("The scan ticket is too large.".into());
        }
        let parsed: Value =
            serde_json::from_str(ticket).map_err(|_| "The scan ticket is invalid.")?;
        let scan_id = parsed["scan_id"]
            .as_str()
            .filter(|id| id.len() == 36)
            .ok_or("The scan ticket is invalid.")?;
        let challenge = parsed["challenge"]
            .as_str()
            .filter(|token| {
                token.len() == 43
                    && token
                        .bytes()
                        .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
            })
            .ok_or("The scan ticket is invalid.")?;

        let model = sysctl("hw.model");
        let memory = sysctl("hw.memsize")
            .and_then(|size| size.parse::<u64>().ok())
            .filter(|size| *size > 0)
            .map(|bytes| bytes.div_ceil(1 << 30));
        let cpu: Vec<_> = sysctl("machdep.cpu.brand_string").into_iter().collect();
        if model.is_none() && memory.is_none() && cpu.is_empty() {
            return Err("macOS did not return supported hardware readings.".into());
        }
        Ok(json!({
            "scan_id": scan_id,
            "challenge": challenge,
            "platform": "macos",
            "hardware": {
                "manufacturer": "Apple",
                "model": model,
                "cpu": cpu,
                "gpu": [],
                "memory_gib": memory,
                "drives": []
            }
        }))
    }
}
