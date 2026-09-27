import csv
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from PIL import Image, ImageTk

from core.models import ImageMetadata, ScanSummary
from core.scanner import ScanEngine


class ImageInspectorApp(tk.Tk):
    def __init__(self, parser: Callable[[Path], ImageMetadata]):
        super().__init__()
        self.title("ImageHeaderLab")
        self.geometry("1280x760")
        self.minsize(980, 620)
        self.option_add("*Font", ("Segoe UI", 10))
        self.engine = ScanEngine(parser)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.scan_thread = None
        self.rows: dict[str, ImageMetadata] = {}
        self.preview_image = None
        self.sort_reverse: dict[str, bool] = {}
        self._configure_styles()
        self._build()
        self.after(50, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=27)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Muted.TLabel", foreground="#5c6673")

    def _build(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Анализатор заголовков изображений", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Ручное чтение JPEG, GIF, TIFF, BMP, PNG и PCX без библиотек метаданных",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(0, 10))
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(controls, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="Выбрать папку", command=self._choose_folder).pack(side="left", padx=(8, 0))
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Включая подпапки", variable=self.recursive_var).pack(side="left", padx=10)
        self.scan_button = ttk.Button(controls, text="Сканировать", command=self._start_scan)
        self.scan_button.pack(side="left")
        self.cancel_button = ttk.Button(controls, text="Отмена", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))
        self.export_button = ttk.Button(controls, text="Экспорт CSV", command=self._export, state="disabled")
        self.export_button.pack(side="left", padx=(8, 0))

        progress_frame = ttk.Frame(root)
        progress_frame.pack(fill="x", pady=(0, 10))
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(progress_frame, text="Готово", width=28, anchor="e")
        self.progress_label.pack(side="left", padx=(10, 0))

        split = ttk.Panedwindow(root, orient="vertical")
        split.pack(fill="both", expand=True)
        table_frame = ttk.Frame(split)
        details_frame = ttk.Frame(split, padding=(0, 8, 0, 0))
        split.add(table_frame, weight=4)
        split.add(details_frame, weight=2)

        columns = ("name", "format", "size", "dpi", "depth", "compression", "read", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        labels = {
            "name": "Файл",
            "format": "Формат",
            "size": "Размер, px",
            "dpi": "Разрешение",
            "depth": "Глубина",
            "compression": "Сжатие",
            "read": "Прочитано",
            "status": "Статус",
        }
        widths = {"name": 250, "format": 75, "size": 110, "dpi": 135, "depth": 145, "compression": 180, "read": 125, "status": 270}
        for column in columns:
            self.tree.heading(column, text=labels[column], command=lambda c=column: self._sort(c))
            self.tree.column(column, width=widths[column], minwidth=60, anchor="w", stretch=column in {"name", "status"})
        self.tree.tag_configure("damaged", foreground="#b3261e")
        self.tree.tag_configure("warning", foreground="#8a5600")
        self.tree.tag_configure("ok", foreground="#126a3a")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        preview_box = ttk.LabelFrame(details_frame, text="Предпросмотр", padding=8)
        preview_box.pack(side="left", fill="both", padx=(0, 8))
        self.preview = ttk.Label(preview_box, text="Выберите строку", anchor="center", width=34)
        self.preview.pack(fill="both", expand=True)
        info_box = ttk.LabelFrame(details_frame, text="Сведения", padding=8)
        info_box.pack(side="left", fill="both", expand=True)
        self.details = tk.Text(info_box, height=9, wrap="word", relief="flat", background="#f7f7f7")
        self.details.pack(fill="both", expand=True)
        self.details.configure(state="disabled")

    def _choose_folder(self):
        selected = filedialog.askdirectory(title="Выберите папку с изображениями")
        if selected:
            self.folder_var.set(selected)

    def _start_scan(self):
        folder = Path(self.folder_var.get().strip())
        if not folder.is_dir():
            messagebox.showwarning("Папка не выбрана", "Укажите существующую папку.")
            return
        if self.scan_thread and self.scan_thread.is_alive():
            return
        self.stop_event.clear()
        self.rows.clear()
        self.tree.delete(*self.tree.get_children())
        self.preview.configure(image="", text="Выберите строку")
        self.preview_image = None
        self._set_details("")
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(12)
        self.progress_label.configure(text="Подготовка списка файлов")
        self.scan_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.export_button.configure(state="disabled")
        self.scan_thread = threading.Thread(
            target=self._run_scan,
            args=(folder, self.recursive_var.get()),
            daemon=True,
            name="scan-coordinator",
        )
        self.scan_thread.start()

    def _run_scan(self, folder: Path, recursive: bool):
        try:
            summary = self.engine.scan(
                folder,
                recursive,
                self.stop_event,
                lambda item, done, total: self.events.put(("result", item, done, total)),
                lambda text, total: self.events.put(("state", text, total)),
            )
            self.events.put(("done", summary))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _poll(self):
        processed = 0
        while processed < 250:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if event[0] == "state":
                _, text, total = event
                self.progress_label.configure(text=text)
                if total:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=total, value=0)
            elif event[0] == "result":
                _, item, done, total = event
                self._insert(item)
                self.progress.configure(value=done, maximum=max(total, 1))
                self.progress_label.configure(text=f"{done} из {total}")
            elif event[0] == "done":
                self._finish(event[1])
            elif event[0] == "error":
                self._finish_error(event[1])
        self.after(50, self._poll)

    def _insert(self, item: ImageMetadata):
        iid = str(len(self.rows) + 1)
        self.rows[iid] = item
        if item.status == "Файл повреждён" or item.status == "Ошибка доступа":
            tag = "damaged"
        elif item.status.startswith("Предупреждение") or item.status.startswith("Подменённое"):
            tag = "warning"
        else:
            tag = "ok"
        self.tree.insert(
            "",
            "end",
            iid=iid,
            values=(
                item.file_name,
                item.format_name,
                item.dimensions,
                item.resolution,
                item.color_depth,
                item.compression,
                item.read_ratio,
                item.status,
            ),
            tags=(tag,),
        )

    def _finish(self, summary: ScanSummary):
        self.progress.stop()
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.export_button.configure(state="normal" if self.rows else "disabled")
        if summary.cancelled:
            text = f"Остановлено: {summary.completed} из {summary.total}"
        else:
            text = f"{summary.completed} файлов за {summary.elapsed:.2f} с"
        self.progress_label.configure(text=text)
        ratio = summary.bytes_read * 100 / summary.total_size if summary.total_size else 0
        self._set_details(
            f"Обработано: {summary.completed}\n"
            f"Корректных: {summary.valid}\n"
            f"Повреждённых: {summary.damaged}\n"
            f"Неизвестных: {summary.unsupported}\n"
            f"Прочитано с диска: {self._format_bytes(summary.bytes_read)} из {self._format_bytes(summary.total_size)} ({ratio:.2f} %)"
        )

    def _finish_error(self, text: str):
        self.progress.stop()
        self.scan_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.progress_label.configure(text="Ошибка")
        messagebox.showerror("Ошибка сканирования", text)

    def _cancel(self):
        self.stop_event.set()
        self.cancel_button.configure(state="disabled")
        self.progress_label.configure(text="Остановка")

    def _select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        item = self.rows[selection[0]]
        lines = [
            f"Путь: {item.path}",
            f"Формат: {item.format_name}",
            f"Размер: {item.dimensions}",
            f"Разрешение: {item.resolution}",
            f"Глубина цвета: {item.color_depth}",
            f"Сжатие: {item.compression}",
            f"Статус: {item.status}",
            f"Размер файла: {self._format_bytes(item.file_size)}",
            f"Считано парсером: {item.read_ratio}",
        ]
        lines.extend(f"{name}: {value}" for name, value in item.details.items())
        self._set_details("\n".join(lines))
        try:
            with Image.open(item.path) as image:
                image.thumbnail((330, 210))
                rendered = image.convert("RGBA")
                self.preview_image = ImageTk.PhotoImage(rendered)
            self.preview.configure(image=self.preview_image, text="")
        except Exception:
            self.preview_image = None
            self.preview.configure(image="", text="Предпросмотр недоступен")

    def _set_details(self, text: str):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def _sort(self, column: str):
        reverse = self.sort_reverse.get(column, False)
        items = [(self.tree.set(iid, column), iid) for iid in self.tree.get_children("")]
        items.sort(key=lambda pair: pair[0].casefold(), reverse=reverse)
        for index, (_, iid) in enumerate(items):
            self.tree.move(iid, "", index)
        self.sort_reverse[column] = not reverse

    def _export(self):
        target = filedialog.asksaveasfilename(
            title="Сохранить таблицу",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not target:
            return
        with open(target, "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Файл", "Формат", "Размер", "Разрешение", "Глубина", "Сжатие", "Прочитано", "Статус", "Путь"])
            for iid in self.tree.get_children(""):
                item = self.rows[iid]
                writer.writerow(
                    [item.file_name, item.format_name, item.dimensions, item.resolution, item.color_depth, item.compression, item.read_ratio, item.status, item.path]
                )

    @staticmethod
    def _format_bytes(value: int) -> str:
        number = float(value)
        for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
            if number < 1024 or unit == "ТБ":
                return f"{number:.2f} {unit}"
            number /= 1024
        return f"{number:.2f} ТБ"

    def _close(self):
        self.stop_event.set()
        self.destroy()

