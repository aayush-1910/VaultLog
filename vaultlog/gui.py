"""Minimal Tkinter GUI for VaultLog."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .cli import MIN_PASSWORD_LEN
from .config import default_vault_path
from .vault import Entry, Vault, VaultError, WrongPasswordError

AUTO_LOCK_MS = 10 * 60 * 1000  # lock after 10 minutes of inactivity


class UnlockDialog(tk.Toplevel):
    """Asks for the password (and confirmation when creating a new vault)."""

    def __init__(self, master: tk.Tk, path: Path):
        super().__init__(master)
        self.path = path
        self.vault: Vault | None = None
        self.creating = not Vault.exists(path)

        self.title("VaultLog - " + ("Create vault" if self.creating else "Unlock"))
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=16)
        frm.grid()

        msg = "Create a new vault at:" if self.creating else "Unlock vault:"
        ttk.Label(frm, text=msg).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, text=str(path), foreground="gray").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        ttk.Label(frm, text="Password").grid(row=2, column=0, sticky="w")
        self.pw = ttk.Entry(frm, show="•", width=32)
        self.pw.grid(row=2, column=1, pady=2)
        self.pw2 = None
        if self.creating:
            ttk.Label(frm, text="Confirm").grid(row=3, column=0, sticky="w")
            self.pw2 = ttk.Entry(frm, show="•", width=32)
            self.pw2.grid(row=3, column=1, pady=2)

        self.error = ttk.Label(frm, text="", foreground="#c0392b")
        self.error.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Quit", command=self.destroy).pack(side="right")
        ttk.Button(
            btns, text="Create" if self.creating else "Unlock", command=self.submit
        ).pack(side="right", padx=6)

        self.bind("<Return>", lambda _e: self.submit())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.pw.focus_set()
        self.grab_set()

    def submit(self) -> None:
        pw = self.pw.get()
        try:
            if self.creating:
                if len(pw) < MIN_PASSWORD_LEN:
                    raise VaultError(f"Use at least {MIN_PASSWORD_LEN} characters")
                if pw != self.pw2.get():
                    raise VaultError("Passwords do not match")
                self.vault = Vault.create(self.path, pw)
            else:
                self.config(cursor="watch")
                self.update_idletasks()
                self.vault = Vault.open(self.path, pw)
        except WrongPasswordError:
            self._fail("Incorrect password")
            return
        except VaultError as exc:
            self._fail(str(exc))
            return
        finally:
            self.config(cursor="")
        self.destroy()

    def _fail(self, msg: str) -> None:
        self.error.config(text=msg)
        self.pw.delete(0, "end")
        if self.pw2 is not None:
            self.pw2.delete(0, "end")
        self.pw.focus_set()


class JournalApp:
    def __init__(self, root: tk.Tk, vault: Vault):
        self.root = root
        self.vault = vault
        self.current: Entry | None = None
        self._entries: dict[str, Entry] = {}
        self._dirty = False
        self._lock_job: str | None = None
        self.locked = False
        self.quitting = False

        root.title(f"VaultLog - {vault.path.name}")
        root.geometry("960x600")
        root.minsize(700, 400)
        self._build()
        self.refresh()
        self.new_entry()

        for seq in ("<Key>", "<Button>", "<Motion>"):
            root.bind_all(seq, self._reset_lock_timer, add="+")
        self._reset_lock_timer()
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ------------------------------------------------------------ layout
    def _build(self) -> None:
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left side: search + list
        left = ttk.Frame(paned, padding=8)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        search = ttk.Entry(left, textvariable=self.search_var)
        search.pack(fill="x")
        ttk.Label(left, text="Search: words or tag:name", foreground="gray").pack(anchor="w")

        self.tree = ttk.Treeview(left, columns=("date", "title"), show="headings")
        self.tree.heading("date", text="Date")
        self.tree.heading("title", text="Entry")
        self.tree.column("date", width=120, stretch=False)
        self.tree.column("title", width=220)
        self.tree.pack(fill="both", expand=True, pady=(6, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.count_lbl = ttk.Label(left, text="")
        self.count_lbl.pack(anchor="w", pady=(4, 0))
        paned.add(left, weight=1)

        # Right side: editor
        right = ttk.Frame(paned, padding=8)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)

        ttk.Label(right, text="Title").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="Tags").grid(row=1, column=0, sticky="w")
        self.tags_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.tags_var).grid(row=1, column=1, sticky="ew", pady=2)
        for var in (self.title_var, self.tags_var):
            var.trace_add("write", lambda *_: self._mark_dirty())

        self.meta_lbl = ttk.Label(right, text="", foreground="gray")
        self.meta_lbl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 4))

        body_frame = ttk.Frame(right)
        body_frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.body = tk.Text(body_frame, wrap="word", undo=True, font=("Segoe UI", 11), padx=8, pady=8)
        sb = ttk.Scrollbar(body_frame, command=self.body.yview)
        self.body.configure(yscrollcommand=sb.set)
        self.body.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.body.bind("<<Modified>>", self._on_body_modified)

        btns = ttk.Frame(right)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="New (Ctrl+N)", command=self.new_entry).pack(side="left")
        ttk.Button(btns, text="Save (Ctrl+S)", command=self.save).pack(side="left", padx=6)
        ttk.Button(btns, text="Delete", command=self.delete).pack(side="left")
        ttk.Button(btns, text="Lock", command=self.lock).pack(side="right")
        paned.add(right, weight=3)

        self.root.bind("<Control-s>", lambda _e: self.save())
        self.root.bind("<Control-n>", lambda _e: self.new_entry())
        self.root.bind("<Control-f>", lambda _e: search.focus_set())

    # ------------------------------------------------------------ state
    def _mark_dirty(self) -> None:
        self._dirty = True

    def _on_body_modified(self, _e=None) -> None:
        if self.body.edit_modified():
            self._dirty = True
            self.body.edit_modified(False)

    def _confirm_discard(self) -> bool:
        if not self._dirty or not self.body.get("1.0", "end").strip():
            return True
        return messagebox.askyesno("Unsaved changes", "Discard unsaved changes?", parent=self.root)

    def refresh(self) -> None:
        q = self.search_var.get() if hasattr(self, "search_var") else ""
        try:
            items = self.vault.search(q)
        except VaultError as exc:
            messagebox.showerror("Error", str(exc), parent=self.root)
            return
        self._entries = {e.id: e for e in items}
        self.tree.delete(*self.tree.get_children())
        for e in items:
            self.tree.insert("", "end", iid=e.id, values=(e.local_time(), e.display_title))
        total = len(self.vault)
        self.count_lbl.config(text=f"{len(items)} of {total} entries" if q else f"{total} entries")
        if self.current and self.current.id in self._entries:
            self.tree.selection_set(self.current.id)

    def _load(self, entry: Entry | None) -> None:
        self.current = entry
        self.title_var.set(entry.title if entry else "")
        self.tags_var.set(", ".join(entry.tags) if entry else "")
        self.body.delete("1.0", "end")
        if entry:
            self.body.insert("1.0", entry.body)
            meta = f"Created {entry.local_time()}"
            if entry.updated_at != entry.created_at:
                meta += f"  ·  Updated {entry.local_time('updated_at')}"
            self.meta_lbl.config(text=meta)
        else:
            self.meta_lbl.config(text="New entry - timestamp is added when you save")
        self.body.edit_reset()
        self.body.edit_modified(False)
        self._dirty = False
        self.body.focus_set()

    def _on_select(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel or (self.current and sel[0] == self.current.id):
            return
        if not self._confirm_discard():
            if self.current:
                self.tree.selection_set(self.current.id)
            else:
                self.tree.selection_remove(sel)
            return
        self._load(self._entries.get(sel[0]))

    # ------------------------------------------------------------ actions
    def new_entry(self) -> None:
        if not self._confirm_discard():
            return
        self.tree.selection_remove(self.tree.selection())
        self._load(None)

    def save(self) -> None:
        body = self.body.get("1.0", "end-1c")
        if not body.strip():
            messagebox.showwarning("Empty entry", "Write something before saving.", parent=self.root)
            return
        tags = [t for t in self.tags_var.get().split(",") if t.strip()]
        if self.current is None:
            entry = self.vault.add(body, title=self.title_var.get(), tags=tags)
        else:
            self.current.body = body
            self.current.title = self.title_var.get().strip()
            self.current.tags = tags
            entry = self.vault.update(self.current)
        self.current = entry
        self.refresh()
        self._load(entry)

    def delete(self) -> None:
        if self.current is None:
            self._load(None)
            return
        if not messagebox.askyesno(
            "Delete entry", f"Delete '{self.current.display_title}' permanently?", parent=self.root
        ):
            return
        self.vault.delete(self.current.id)
        self.current = None
        self.refresh()
        self._load(None)

    def _reset_lock_timer(self, _e=None) -> None:
        if self.locked:
            return
        if self._lock_job:
            self.root.after_cancel(self._lock_job)
        self._lock_job = self.root.after(AUTO_LOCK_MS, self.lock)

    def lock(self) -> None:
        """Close the vault (wiping the key from this object) and return to the unlock screen."""
        if self.locked:
            return
        self.locked = True
        if self._lock_job:
            self.root.after_cancel(self._lock_job)
        self.vault.close()
        self.root.quit()

    def quit(self) -> None:
        if not self._confirm_discard():
            return
        self.quitting = True
        self.lock()


def run(path: str | Path | None = None) -> None:
    path = Path(path) if path else default_vault_path()
    root = tk.Tk()
    root.withdraw()
    try:
        ttk.Style().theme_use("vista" if "vista" in ttk.Style().theme_names() else "clam")
    except tk.TclError:
        pass

    while True:
        dlg = UnlockDialog(root, path)
        root.wait_window(dlg)
        if dlg.vault is None:
            break
        root.deiconify()
        app = JournalApp(root, dlg.vault)
        root.mainloop()
        # mainloop returns on lock or quit
        for child in root.winfo_children():
            child.destroy()
        root.unbind_all("<Key>")
        root.unbind_all("<Button>")
        root.unbind_all("<Motion>")
        root.withdraw()
        if app.quitting:
            break
    root.destroy()


if __name__ == "__main__":
    run()
