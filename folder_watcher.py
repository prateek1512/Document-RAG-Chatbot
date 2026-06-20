# folder_watcher.py
# monitors a local directory for file changes and automatically keeps
# the RAG vector database in sync


import sys
import os
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.database.connection import engine, Base
from app.services.vector_store_service import load_index
from app.services.sync_service import (
    handle_new_file,
    handle_modified_file,
    handle_deleted_file,
)


# CONFIG

WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./data")
# Only process files with these extensions.
SUPPORTED_EXTENSIONS = {".pdf", ".csv", ".json", ".docx", ".txt", ".md"}


# EVENT HANDLER
# watchdog calls these methods whenever something happens in the folder.


class SyncHandler(FileSystemEventHandler):

    def _is_supported(self, file_path: str) -> bool:
        _, ext = os.path.splitext(file_path)
        return ext.lower() in SUPPORTED_EXTENSIONS

    # NEW FILE
    def on_created(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not self._is_supported(file_path):
            return

        print(f"\n{'─'*50}")
        print(f"NEW FILE DETECTED: {file_path}")
        print(f"{'─'*50}")

        # A small delay ensures the file content is fully flushed to disk.
        time.sleep(1)

        try:
            handle_new_file(file_path)
        except Exception as e:
            print(f"Error ingesting '{file_path}': {e}")

    # MODIFIED FILE
    def on_modified(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not self._is_supported(file_path):
            return

        print(f"\n{'─'*50}")
        print(f"FILE MODIFIED: {file_path}")
        print(f"{'─'*50}")

        # Same small delay to let the write finish
        time.sleep(1)

        try:
            # handle_modified_file compares the content hash first.
            # If the hash hasn't changed, it skips re-ingestion entirely.
            handle_modified_file(file_path)
        except Exception as e:
            print(f"Error re-syncing '{file_path}': {e}")

    # DELETED FILE
    def on_deleted(self, event):
        if event.is_directory:
            return

        file_path = event.src_path

        if not self._is_supported(file_path):
            return

        print(f"\n{'─'*50}")
        print(f"FILE DELETED: {file_path}")
        print(f"{'─'*50}")

        try:
            handle_deleted_file(file_path)
        except Exception as e:
            print(f"Error cleaning up '{file_path}': {e}")


# MAIN — start watching

if __name__ == "__main__":
    # Create database tables if they don't exist yet
    Base.metadata.create_all(bind=engine)

    # Load the FAISS index from disk (no-op for Pinecone)
    load_index()

    # Make sure the watch folder exists
    os.makedirs(WATCH_FOLDER, exist_ok=True)

    # Create the observer
    # This monitors the watch folder for changes
    observer = Observer()
    observer.schedule(
        SyncHandler(),
        path=WATCH_FOLDER,
        recursive=False,  # Set to True if you want to watch subfolders too
    )

    print("=" * 55)
    print(f"  WATCHING: {os.path.abspath(WATCH_FOLDER)}")
    print(f"  Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    print(f"  Press Ctrl+C to stop")
    print("=" * 55)
    print()

    # Start and run until interrupted
    observer.start()

    try:
        # The observer runs in a daemon thread, so we need to keep
        # the main thread alive. We just sleep in a loop.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping watcher...")
        observer.stop()

    # Wait for the observer thread to finish cleanly
    observer.join()
    print("👋  Watcher stopped.")
