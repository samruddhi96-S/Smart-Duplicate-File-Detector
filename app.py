import concurrent.futures
import hashlib
import os
import sqlite3
import time
from pathlib import Path
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Smart Duplicate File Detector",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- AESTHETIC DARK TECH THEME (CSS) ---
st.markdown("""
    <style>
    .stApp {
        background-color: #010409;
        color: #e6edf3;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: 
            radial-gradient(circle at 70% 20%, rgba(56, 189, 248, 0.15) 0%, transparent 40%),
            radial-gradient(circle at 30% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 40%);
        z-index: -1;
    }
    h1 {
        color: #38bdf8 !important;
        font-weight: 800;
        letter-spacing: -0.75px;
        text-shadow: 0 0 12px rgba(56, 189, 248, 0.6);
    }
    p, label {
        color: #94a3b8 !important;
        font-size: 1.1rem;
    }
    .stTextInput input {
        background-color: #0d1117;
        color: #ffffff;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 12px;
        font-size: 1rem;
    }
    .stTextInput input:focus {
        border-color: #38bdf8;
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }
    .stButton button {
        background: linear-gradient(135deg, #166534 0%, #15803d 100%);
        color: white;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        padding: 0.7rem 1.4rem;
        width: 100%;
        font-size: 1.1rem;
        box-shadow: 0 4px 15px rgba(22, 101, 52, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stButton button:hover {
        background: linear-gradient(135deg, #15803d 0%, #16a34a 100%);
        box-shadow: 0 8px 20px rgba(21, 128, 61, 0.5);
        transform: translateY(-2px);
    }
    div[data-testid="stMetric"] {
        background-color: #0d1117;
        border: 1px solid #30363d;
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 6px 12px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 1rem !important;
    }
    div[data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-size: 2.2rem !important;
        text-shadow: 0 0 8px rgba(56, 189, 248, 0.4);
    }
    </style>
""", unsafe_allow_html=True)

EXCLUDED_DIRS = {'node_modules', '.git', '__pycache__', 'venv', 'env', '$RECYCLE.BIN', 'System Volume Information'}

# --- 1. SETUP SQLITE CACHE ---
def init_db():
    conn = sqlite3.connect("file_cache.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            path TEXT PRIMARY KEY,
            size INTEGER,
            mtime REAL,
            partial_hash TEXT
        )
    """)
    conn.commit()
    conn.close()

# --- 2. LIGHTNING-FAST HASH ---
def get_partial_hash(file_path, chunk_size=4096):
    hasher = hashlib.sha256()
    try:
        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            hasher.update(f.read(chunk_size))
            if file_size > chunk_size:
                f.seek(-chunk_size, os.SEEK_END)
                hasher.update(f.read(chunk_size))
        return hasher.hexdigest()
    except Exception:
        return None

def process_file(file_path):
    conn = sqlite3.connect("file_cache.db")
    cursor = conn.cursor()
    try:
        stat = os.stat(file_path)
        size = stat.st_size
        mtime = stat.st_mtime
    except Exception:
        conn.close()
        return None

    cursor.execute("SELECT mtime, partial_hash FROM file_cache WHERE path = ?", (file_path,))
    cached = cursor.fetchone()

    if cached and cached[0] == mtime:
        conn.close()
        return {"path": file_path, "size": size, "partial_hash": cached[1]}

    p_hash = get_partial_hash(file_path)

    cursor.execute("""
        INSERT OR REPLACE INTO file_cache (path, size, mtime, partial_hash)
        VALUES (?, ?, ?, ?)
    """, (file_path, size, mtime, p_hash))
    conn.commit()
    conn.close()

    return {"path": file_path, "size": size, "partial_hash": p_hash}

def scan_search_space(search_root):
    init_db()
    file_list = []
    for root, dirs, files in os.walk(search_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for file in files:
            file_list.append(os.path.join(root, file))

    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_file, path) for path in file_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
    return results

# --- 3. STREAMLIT USER INTERFACE ---
st.title("⚡ Smart Duplicate File Detector")
st.markdown("Find where identical files (different names, same content) are hidden across your device.")

st.markdown("<br>", unsafe_allow_html=True)

# User inputs a specific file path now!
target_file_input = st.text_input("📁 Enter Specific File Path (e.g., C:\\Users\\samru\\Desktop\\Folder1\\AgenticAI.pdf):", "")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 Find Where This File Exists"):
    clean_path = target_file_input.strip('"') # Automatically remove quotes if copied via "Copy as path"
    
    if not os.path.isfile(clean_path):
        st.error("⚠️ Please enter a valid, existing file path (Make sure to include the filename at the end).")
    else:
        with st.spinner("🔍 Scanning storage and matching content hashes..."):
            start_time = time.time()
            
            # Get target file's hash
            target_hash = get_partial_hash(clean_path)
            target_size = os.path.getsize(clean_path)
            
            # Determine search root (We scan the parent drive or user folder to find duplicates)
            # To make it fast and thorough, we scan the drive/folder where this file lives
            drive_root = os.path.splitdrive(clean_path)[0] + "\\" if os.path.splitdrive(clean_path)[0] else "C:\\"
            
            # Scan files in that drive/parent space
            scanned_files = scan_search_space(os.path.dirname(os.path.dirname(clean_path))) # Scans broader parent directory
            
            # Find all files with the same hash
            matching_files = []
            for file_info in scanned_files:
                if file_info["partial_hash"] == target_hash and file_info["size"] == target_size:
                    matching_files.append(file_info["path"])
            
            elapsed = time.time() - start_time

        st.success(f"✨ Search completed successfully in {elapsed:.2f} seconds!")

        st.markdown("---")
        if len(matching_files) <= 1:
            st.info(f"✅ **No duplicates found!** The file `{os.path.basename(clean_path)}` is unique in this directory.")
        else:
            st.metric(label="Total Identical Copies Found", value=len(matching_files))
            st.warning(f"⚠️ The same file content was found in **{len(matching_files)} different places** (even with different names):")
            
            st.markdown("### 📍 File Locations & Names:")
            for i, match_p in enumerate(matching_files, 1):
                f_name = os.path.basename(match_p)
                f_dir = os.path.dirname(match_p)
                is_target = " (Target File)" if os.path.normpath(match_p) == os.path.normpath(clean_path) else ""
                st.markdown(f"**{i}. File Name:** `{f_name}`{is_target}")
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📍 **Location:** `{f_dir}`")