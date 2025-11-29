import os
import shutil

# --- CONFIGURATION ---
# NOTE: SOURCE_DIR is the project root that contains the `Raavi/` package.
SOURCE_DIR = r"D:\Raavi_Refraction\Raavi_refraction"
DEST_DIR = r"D:\Diba"

# Items to explicitly copy (Files & Directories) from SOURCE_DIR to DEST_DIR.
# Focus on everything we have modified/added in the Raavi engine.
ITEMS_TO_COPY = [
    "Raavi",             # Main Raavi package (includes logic + Raavi/tests + README + pyproject)
    "demo_chart.py",     # Demo script
    "migrate_raavi.py",  # Migration script itself (optional, for reuse)
    # Add "demo_panchanga.py" here if/when it is created.
]

# Patterns to ALWAYS ignore (Safety Filter)
IGNORE_PATTERNS = shutil.ignore_patterns(
    ".git",
    ".github",
    "__pycache__",
    "*.pyc",
    "build",
    "dist",
    "*.egg-info",
    ".venv",
    "venv",
)


def safe_copy() -> None:
    print(f"🚀 Starting Migration: {SOURCE_DIR} -> {DEST_DIR}")

    if not os.path.exists(SOURCE_DIR):
        print(f"❌ Source directory does not exist: {SOURCE_DIR}")
        return

    if not os.path.exists(DEST_DIR):
        print(f"⚠️ Destination directory does not exist. Creating: {DEST_DIR}")
        os.makedirs(DEST_DIR)

    for item in ITEMS_TO_COPY:
        s_item = os.path.join(SOURCE_DIR, item)
        d_item = os.path.join(DEST_DIR, item)

        if not os.path.exists(s_item):
            print(f"⚠️ Skipping missing item: {item}")
            continue

        print(f"📦 Copying: {item}...")

        if os.path.isdir(s_item):
            # Copy directory (recursive), cleaning any existing version at dest
            if os.path.exists(d_item):
                shutil.rmtree(d_item)
            shutil.copytree(s_item, d_item, ignore=IGNORE_PATTERNS)
        else:
            # Copy single file
            shutil.copy2(s_item, d_item)

    print("\n✅ Migration Complete Successfully!")
    print("👉 Next Step: Go to D:\\Diba, check 'git status', and commit on a new branch.")


if __name__ == "__main__":
    safe_copy()
