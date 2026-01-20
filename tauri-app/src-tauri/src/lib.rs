use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::path::PathBuf;
use std::io::{BufRead, BufReader};
use std::thread;
use std::net::TcpStream;
use tauri::{Manager, RunEvent};

struct BackendProcess(Mutex<Option<Child>>);

/// 获取后端可执行文件路径
fn get_backend_path() -> Option<PathBuf> {
    let exe_path = std::env::current_exe().ok()?;
    let exe_dir = exe_path.parent()?;
    
    // Tauri sidecar 命名: name-target_triple
    // 在 macOS 上会去掉后缀，直接用 name
    let possible_names = vec![
        "ytmusic-backend",
        "ytmusic-backend-aarch64-apple-darwin",
        "ytmusic-backend-x86_64-apple-darwin",
    ];
    
    for name in &possible_names {
        let path = exe_dir.join(name);
        if path.exists() {
            println!("[Backend] Found: {:?}", path);
            return Some(path);
        }
    }
    
    // 开发模式
    let dev_path = std::env::current_dir().ok()?.join("dist/ytmusic-backend");
    if dev_path.exists() {
        println!("[Backend] Found (dev): {:?}", dev_path);
        return Some(dev_path);
    }
    
    None
}

/// 获取 yt-dlp 路径
fn get_ytdlp_path() -> Option<PathBuf> {
    let exe_path = std::env::current_exe().ok()?;
    let exe_dir = exe_path.parent()?;
    
    let possible_names = vec![
        "yt-dlp",
        "yt-dlp-aarch64-apple-darwin",
        "yt-dlp-x86_64-apple-darwin",
    ];
    
    for name in &possible_names {
        let path = exe_dir.join(name);
        if path.exists() {
            return Some(path);
        }
    }
    
    // 开发模式
    let dev_path = std::env::current_dir().ok()?.join("yt-dlp_macos");
    if dev_path.exists() {
        return Some(dev_path);
    }
    
    None
}

/// 获取工作目录（存放下载文件等）
fn get_data_dir() -> PathBuf {
    // 优先使用用户数据目录
    if let Some(data_dir) = dirs::data_local_dir() {
        let app_dir = data_dir.join("ytmusic-downloader");
        let _ = std::fs::create_dir_all(&app_dir);
        return app_dir;
    }
    
    // 回退到当前目录
    std::env::current_dir().unwrap_or_default()
}

/// 启动后端服务器
fn start_backend_server() -> Option<Child> {
    println!("[Backend] ====================================");
    println!("[Backend] Starting backend server...");
    
    // 获取路径
    let backend_path = get_backend_path();
    let ytdlp_path = get_ytdlp_path();
    let data_dir = get_data_dir();
    
    println!("[Backend] Backend: {:?}", backend_path);
    println!("[Backend] yt-dlp: {:?}", ytdlp_path);
    println!("[Backend] Data dir: {:?}", data_dir);
    
    // 创建必要目录
    let download_dir = data_dir.join("download");
    let jobs_dir = data_dir.join("jobs");
    let _ = std::fs::create_dir_all(&download_dir);
    let _ = std::fs::create_dir_all(&jobs_dir);
    
    if let Some(backend) = backend_path {
        let mut cmd = Command::new(&backend);
        cmd.env("PORT", "5000")
           .env("DOWNLOAD_DIR", download_dir.to_string_lossy().to_string())
           .env("JOBS_DIR", jobs_dir.to_string_lossy().to_string())
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());
        
        if let Some(ytdlp) = &ytdlp_path {
            cmd.env("YTDLP_BIN", ytdlp.to_string_lossy().to_string());
        }
        
        match cmd.spawn() {
            Ok(mut child) => {
                println!("[Backend] Started with PID: {}", child.id());
                
                // 读取输出用于调试
                if let Some(stdout) = child.stdout.take() {
                    thread::spawn(move || {
                        let reader = BufReader::new(stdout);
                        for line in reader.lines().take(50) {
                            if let Ok(line) = line {
                                println!("[Backend] {}", line);
                            }
                        }
                    });
                }
                
                if let Some(stderr) = child.stderr.take() {
                    thread::spawn(move || {
                        let reader = BufReader::new(stderr);
                        for line in reader.lines().take(50) {
                            if let Ok(line) = line {
                                eprintln!("[Backend ERR] {}", line);
                            }
                        }
                    });
                }
                
                return Some(child);
            }
            Err(e) => {
                eprintln!("[Backend] Failed to start: {}", e);
            }
        }
    }
    
    // 回退到 Python（开发模式）
    println!("[Backend] Trying Python fallback...");
    let python = if cfg!(target_os = "windows") { "python" } else { "python3" };
    
    if let Ok(cwd) = std::env::current_dir() {
        let app_py = cwd.join("app.py");
        if app_py.exists() {
            match Command::new(python)
                .arg("app.py")
                .current_dir(&cwd)
                .env("PORT", "5000")
                .spawn()
            {
                Ok(child) => {
                    println!("[Backend] Python started with PID: {}", child.id());
                    return Some(child);
                }
                Err(e) => {
                    eprintln!("[Backend] Python failed: {}", e);
                }
            }
        }
    }
    
    eprintln!("[Backend] All methods failed!");
    None
}

/// 停止后端服务器
fn stop_backend_server(process: &Mutex<Option<Child>>) {
    if let Ok(mut guard) = process.lock() {
        if let Some(ref mut child) = *guard {
            println!("[Backend] Stopping (PID: {})...", child.id());
            let _ = child.kill();
            let _ = child.wait();
            println!("[Backend] Stopped");
        }
        *guard = None;
    }
}

/// 等待后端就绪
fn wait_for_backend(timeout_secs: u64) -> bool {
    println!("[Backend] Waiting for server...");
    let start = std::time::Instant::now();
    let timeout = std::time::Duration::from_secs(timeout_secs);
    
    while start.elapsed() < timeout {
        if TcpStream::connect("127.0.0.1:5000").is_ok() {
            println!("[Backend] Server is ready!");
            return true;
        }
        thread::sleep(std::time::Duration::from_millis(100));
    }
    
    eprintln!("[Backend] Timeout waiting for server");
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    println!("[App] YouTube Music Downloader starting...");
    
    let backend = BackendProcess(Mutex::new(start_backend_server()));
    
    // 等待后端启动
    if !wait_for_backend(15) {
        eprintln!("[App] Warning: Backend may not be ready");
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(backend)
        .build(tauri::generate_context!())
        .expect("Failed to build app")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                println!("[App] Exiting...");
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    stop_backend_server(&state.0);
                }
            }
        });
}
