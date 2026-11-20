"""Native Windows-friendly Local Network companion.

It hosts NetDrop or discovers LAN hosts. Packaging this module is the next
phase; it intentionally uses tkinter from the Python standard library.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from app.local_discovery import discover_local_hosts


class LocalCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title("NetDrop Local")
        self.root.resizable(False, False)
        self.server = None
        self.hosts = []
        frame = ttk.Frame(root, padding=20)
        frame.grid()
        ttk.Label(frame, text="NetDrop Local", font=("Segoe UI", 18, "bold")).grid(column=0, row=0, sticky="w")
        ttk.Label(frame, text="Create a room or scan this Wi-Fi for a NetDrop host.").grid(column=0, row=1, pady=(4, 14), sticky="w")
        self.host_button = ttk.Button(frame, text="Host a local room", command=self.host_room)
        self.host_button.grid(column=0, row=2, sticky="ew")
        ttk.Button(frame, text="Scan local rooms", command=self.scan).grid(column=0, row=3, pady=(8, 0), sticky="ew")
        self.status = ttk.Label(frame, text="No local server is running.")
        self.status.grid(column=0, row=4, pady=(14, 6), sticky="w")
        self.results = tk.Listbox(frame, height=6, width=52)
        self.results.grid(column=0, row=5, sticky="ew")
        self.results.bind("<Double-Button-1>", lambda _event: self.open_selected())
        ttk.Button(frame, text="Open selected host", command=self.open_selected).grid(column=0, row=6, pady=(8, 0), sticky="ew")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def host_room(self):
        if self.server and self.server.poll() is None:
            webbrowser.open("http://127.0.0.1:8000")
            return
        environment = os.environ.copy()
        environment["NETDROP_SHARING_MODE"] = "local"
        environment["NETDROP_LOCAL_DISCOVERY"] = "1"
        self.server = subprocess.Popen([sys.executable, "-m", "app.main"], env=environment)
        self.status.config(text="Starting local host…")
        self.root.after(1200, self.open_host)

    def open_host(self):
        if self.server and self.server.poll() is None:
            self.status.config(text="Hosting locally. Keep NetDrop Local open while sharing.")
            webbrowser.open("http://127.0.0.1:8000")
        else:
            self.status.config(text="The local host could not start. Check whether port 8000 is already in use.")

    def scan(self):
        self.status.config(text="Scanning the local network…")
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        try:
            hosts = discover_local_hosts()
        except RuntimeError as error:
            self.root.after(0, lambda: self.status.config(text=str(error)))
            return
        self.root.after(0, lambda: self.show_hosts(hosts))

    def show_hosts(self, hosts):
        self.hosts = hosts
        self.results.delete(0, tk.END)
        for host in hosts:
            self.results.insert(tk.END, f"{host.name} — {host.url}")
        self.status.config(text="Choose a host, then choose its room and enter the PIN." if hosts else "No NetDrop hosts found on this Wi-Fi.")

    def open_selected(self):
        selected = self.results.curselection()
        if not selected:
            messagebox.showinfo("NetDrop Local", "Select a discovered host first.")
            return
        webbrowser.open(self.hosts[selected[0]].url)

    def close(self):
        if self.server and self.server.poll() is None:
            self.server.terminate()
        self.root.destroy()


def main():
    root = tk.Tk()
    LocalCompanion(root)
    root.mainloop()


if __name__ == "__main__":
    main()
