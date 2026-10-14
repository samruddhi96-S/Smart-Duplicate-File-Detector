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

# --- CUSTOM CSS FOR HIGH-TECH AESTHETIC THEME (Updated) ---
st.markdown("""
    <style>
    /* Main Background & Deep Space Aesthetic */
    .stApp {
        background-color: #010409;
        color: #e6edf3;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Background Gradient Effect - Waisa hi subtle visual */
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

    /* Header Styling */
    h1 {
        color: #38bdf8 !important; /* Vivid Blue */
        font-weight: 800;
        letter-spacing: -0.75px;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
    }
    
    p, label {
        color: #94a3b8 !important; /* Subtle Gray */
        font-size: 1.1rem;
    }

    /* Text Input Styling */
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

    /* Custom Button Styling - Waisa hi smooth interaction */
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

    /* Message Boxes Customization */
    div.stSuccess, div.stWarning, div.stInfo, div.stError {
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.06) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2) !important;
    }

    /* Metric Card Customization */
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

    /* Subtle Border on Expander */
    .streamlit-expanderHeader {
        background-color: #0d1117;
        border-radius: 10px;
        color: #e6edf3 !important;
    }
    .streamlit-expanderContent {
        background-color: transparent;
    }
    </style>
""", unsafe_allow_html=True)

EXCLUDED_DIRS = {'node_modules', '.git', '__pycache__', 'venv', 'env'}

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

# --- 2. LIGHTNING-FAST PARTIAL HASH ---
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

# --- 3. MULTI-STAGE PIPELINE ---
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

def scan_folder(folder_path):
    init_db()
    file_list = []
    
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for file in files:
            file_list.append(os.path.join(root, file))

    size_map = {}
    for path in file_list:
        try:
            size = os.path.getsize(path)
            if size > 0:
                size_map.setdefault(size, []).append(path)
        except Exception:
            continue

    potential_duplicates = [paths for size, paths in size_map.items() if len(paths) > 1]
    all_files_to_check = [path for group in potential_duplicates for path in group]

    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_file, path) for path in all_files_to_check]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    return results

# --- 4. STREAMLIT USER INTERFACE ---
# Modernizing the title with an icon
st.title("⚡ Smart Duplicate File Detector")
st.markdown("A high-performance, multi-stage OS-optimized scanning engine with SQLite caching.")

st.markdown("<br>", unsafe_allow_html=True)

# Input container card (styled automatically by CSS)
user_input = st.text_input("📁 Enter Folder Path OR Specific File Path:", str(Path.home() / "Downloads"))

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 Start High-Speed Scan"):
    if os.path.isfile(user_input):
        target_folder = os.path.dirname(user_input)
        target_file_name = os.path.basename(user_input)
    elif os.path.isdir(user_input):
        target_folder = user_input
        target_file_name = None
    else:
        target_folder = None

    if not target_folder or not os.path.isdir(target_folder):
        st.error("⚠️ Please enter a valid folder or file path.")
    else:
        with st.spinner("🔍 Executing multi-stage scan pipeline..."):
            start_time = time.time()
            scanned_files = scan_folder(target_folder)
            
            hash_groups = {}
            for file_info in scanned_files:
                p_hash = file_info["partial_hash"]
                if p_hash:
                    hash_groups.setdefault(p_hash, []).append(file_info["path"])

            duplicates = {h: paths for h, paths in hash_groups.items() if len(paths) > 1}
            elapsed = time.time() - start_time

        st.success(f"✨ Scan completed successfully in {elapsed:.2f} seconds!")

        if target_file_name:
            found_target = False
            for paths in duplicates.values():
                if any(os.path.basename(p).lower() == target_file_name.lower() for p in paths):
                    found_target = True
                    # Re-designing duplicate locations list to be subtle
                    st.warning(f"⚠️ The target file **{target_file_name}** has duplicates!")
                    st.markdown("### 📍 Duplicate File Locations:")
                    for i, p in enumerate(paths, 1):
                        st.markdown(f"**{i}.** `📁 {p}`")
                    break
            if not found_target:
                st.info(f"✅ The file **{target_file_name}** is completely unique. No duplicates found.")
        else:
            duplicate_files = []
            for paths in duplicates.values():
                duplicate_files.extend(paths[1:])

            total_dups_count = len(duplicate_files)

            st.markdown("---")
            if total_dups_count == 0:
                st.info("✅ **No duplicate files found!** Your directory is fully optimized.")
            else:
                # Metric will be styled to glow subtly
                st.metric(label="Total Redundant Duplicate Files", value=total_dups_count)
                st.warning(f"⚠️ Found **{total_dups_count}** duplicate copy file(s) ready for cleanup.")
                
                st.markdown("### 📍 Duplicate File Locations:")
                for i, dup_path in enumerate(duplicate_files, 1):
                    file_name = os.path.basename(dup_path)
                    folder_loc = os.path.dirname(dup_path)
                    st.markdown(f"**{i}. Name:** `{file_name}`")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📍 **Location:** `{folder_loc}`")