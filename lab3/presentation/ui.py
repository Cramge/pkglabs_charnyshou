import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from core.controller import ProcessingController


METHODS = (
    "Медианный фильтр",
    "Максимальный фильтр",
    "Глобальный порог Оцу",
    "Итеративный глобальный порог",
    "Адаптивный порог Сауволы",
)


class ImageProcessingApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ImageProcessingLab — лабораторная работа 3")
        self.root.geometry("1320x850")
        self.root.minsize(1050, 700)
        self.controller = ProcessingController()
        self.events = queue.Queue()
        self.worker = None
        self.original_photo = None
        self.result_photo = None
        self.method = tk.StringVar(value=METHODS[0])
        self.radius = tk.IntVar(value=1)
        self.edge = tk.StringVar(value="Reflect")
        self.window = tk.IntVar(value=75)
        self.k_value = tk.DoubleVar(value=0.15)
        self.tolerance = tk.DoubleVar(value=0.5)
        self.status = tk.StringVar(value="Откройте изображение или выберите тестовый пример")
        self.progress = tk.DoubleVar(value=0)
        self.histogram_summary = tk.StringVar(value="Изменения появятся после обработки")
        self.histogram_before = None
        self.histogram_after = None
        self._configure_style()
        self._build_ui()
        self._update_parameter_state()
        self.root.after(80, self._poll_events)

    def _configure_style(self):
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"), foreground="#183153")
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground="#274c77")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(15, 7))
        style.configure("TButton", padding=(10, 6))
        style.configure("TLabel", font=("Segoe UI", 9))
        style.configure("TCombobox", padding=4)

    def _build_ui(self):
        header = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Обработка цифровых изображений", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Вариант 10", font=("Segoe UI", 10, "bold"), foreground="#2a9d8f").pack(side="right")

        toolbar = ttk.Frame(self.root, padding=(18, 0, 18, 10))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Открыть изображение", command=self._open_image).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="Тестовый пример", command=self._open_sample).pack(side="left", padx=7)
        ttk.Button(toolbar, text="Сохранить результат", command=self._save_result).pack(side="left", padx=7)
        ttk.Button(toolbar, text="Сбросить", command=self._reset).pack(side="left", padx=7)

        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        controls = ttk.Frame(body, padding=14)
        workspace = ttk.Frame(body)
        body.add(controls, weight=0)
        body.add(workspace, weight=1)
        self._build_controls(controls)
        self._build_workspace(workspace)

        footer = ttk.Frame(self.root, padding=(18, 0, 18, 14))
        footer.pack(fill="x")
        self.progress_bar = ttk.Progressbar(footer, variable=self.progress, maximum=100)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(footer, textvariable=self.status, anchor="e").pack(side="right")

    def _build_controls(self, parent):
        parent.configure(width=300)
        parent.pack_propagate(False)
        ttk.Label(parent, text="Метод обработки", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        combo = ttk.Combobox(parent, textvariable=self.method, values=METHODS, state="readonly", width=31)
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda _: self._update_parameter_state())

        separator = ttk.Separator(parent)
        separator.pack(fill="x", pady=14)
        ttk.Label(parent, text="Параметры", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        self.parameter_box = ttk.Frame(parent)
        self.parameter_box.pack(fill="x")
        self.radius_row = self._spin_row(self.parameter_box, "Радиус окна", self.radius, 1, 5, 1)

        self.window_row = self._spin_row(self.parameter_box, "Окно Сауволы", self.window, 3, 151, 2)
        self.k_row = self._spin_row(self.parameter_box, "Коэффициент k", self.k_value, -1.0, 1.0, 0.05)
        self.tolerance_row = self._spin_row(self.parameter_box, "Точность", self.tolerance, 0.1, 10.0, 0.1)
        self.edge_row = ttk.Frame(self.parameter_box)
        ttk.Label(self.edge_row, text="Обработка краев").pack(anchor="w")
        ttk.Combobox(self.edge_row, textvariable=self.edge, values=("Reflect", "Clamp"), state="readonly").pack(fill="x", pady=(3, 0))

        ttk.Separator(parent).pack(fill="x", pady=14)
        self.apply_button = ttk.Button(parent, text="Выполнить обработку", style="Primary.TButton", command=self._start_processing)
        self.apply_button.pack(fill="x", pady=(0, 8))
        self.cancel_button = ttk.Button(parent, text="Отменить", command=self._cancel, state="disabled")
        self.cancel_button.pack(fill="x")

        info = ttk.LabelFrame(parent, text="Реализация", padding=10)
        info.pack(fill="x", pady=(18, 0))
        ttk.Label(info, text="• прямой доступ к байтам\n• ручные алгоритмы\n• Reflect и Clamp\n• параллельные блоки строк", justify="left").pack(anchor="w")

    def _spin_row(self, parent, text, variable, start, end, increment):
        frame = ttk.Frame(parent)
        ttk.Label(frame, text=text).pack(anchor="w")
        ttk.Spinbox(frame, textvariable=variable, from_=start, to=end, increment=increment).pack(fill="x", pady=(3, 0))
        return frame

    def _build_workspace(self, parent):
        images = ttk.Frame(parent)
        images.pack(fill="both", expand=True)
        left = ttk.LabelFrame(images, text="Исходное изображение", padding=8)
        right = ttk.LabelFrame(images, text="Результат", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self.original_label = ttk.Label(left, anchor="center", text="Изображение не выбрано")
        self.result_label = ttk.Label(right, anchor="center", text="Результат появится здесь")
        self.original_label.pack(fill="both", expand=True)
        self.result_label.pack(fill="both", expand=True)

        histograms = ttk.Frame(parent)
        histograms.pack(fill="x", pady=(10, 0))
        self.original_hist = self._histogram_panel(histograms, "Гистограмма до обработки")
        self.result_hist = self._histogram_panel(histograms, "Гистограмма после обработки")
        self.original_hist.master.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.result_hist.master.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self.difference_hist = self._histogram_panel(parent, "Разница гистограмм: после минус до (отдельная шкала)")
        self.difference_hist.configure(height=95)
        self.difference_hist.master.pack(fill="x", pady=(6, 0))
        ttk.Label(parent, textvariable=self.histogram_summary, wraplength=950).pack(fill="x", pady=(3, 0))
        for canvas in (self.original_hist, self.result_hist, self.difference_hist):
            canvas.bind("<Configure>", lambda event: self._redraw_histograms())

    def _histogram_panel(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=6)
        canvas = tk.Canvas(frame, height=120, background="#ffffff", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        return canvas

    def _update_parameter_state(self):
        for frame in (self.radius_row, self.edge_row, self.window_row, self.k_row, self.tolerance_row):
            frame.pack_forget()
        method = self.method.get()
        if method in {"Медианный фильтр", "Максимальный фильтр"}:
            self.radius_row.pack(fill="x", pady=4)
            self.edge_row.pack(fill="x", pady=4)
        elif method == "Итеративный глобальный порог":
            self.tolerance_row.pack(fill="x", pady=4)
        elif method == "Адаптивный порог Сауволы":
            self.window_row.pack(fill="x", pady=4)
            self.k_row.pack(fill="x", pady=4)

    def _parameters(self):
        return {
            "radius": int(self.radius.get()),
            "edge": self.edge.get(),
            "window": int(self.window.get()),
            "k": float(self.k_value.get()),
            "tolerance": float(self.tolerance.get()),
        }

    def _open_image(self):
        path = filedialog.askopenfilename(title="Открыть изображение", filetypes=(("Изображения", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"), ("Все файлы", "*.*")))
        if path:
            self._load(path)

    def _open_sample(self):
        folder = Path(__file__).resolve().parent.parent / "test_images"
        path = filedialog.askopenfilename(initialdir=folder, title="Выберите тестовое изображение", filetypes=(("PNG", "*.png"),))
        if path:
            self._load(path)

    def _load(self, path):
        try:
            image = self.controller.load(path)
        except Exception as error:
            messagebox.showerror("Ошибка", str(error))
            return
        self._show_buffer(image, self.original_label, True)
        self._show_buffer(image, self.result_label, False)
        self._update_histograms(image)
        self.status.set(f"{Path(path).name}: {image.width} × {image.height} px")
        self.progress.set(0)

    def _save_result(self):
        if self.controller.result is None:
            messagebox.showinfo("Сохранение", "Сначала обработайте изображение")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=(("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")))
        if path:
            try:
                self.controller.save(path)
                self.status.set(f"Результат сохранен: {Path(path).name}")
            except Exception as error:
                messagebox.showerror("Ошибка", str(error))

    def _reset(self):
        result = self.controller.reset()
        if result is not None:
            self._show_buffer(result, self.result_label, False)
            self._update_histograms(result)
            self.status.set("Результат сброшен")
            self.progress.set(0)

    def _start_processing(self):
        if self.controller.original is None:
            messagebox.showinfo("Обработка", "Сначала откройте изображение")
            return
        if self.worker and self.worker.is_alive():
            return
        try:
            parameters = self._parameters()
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте значения параметров")
            return
        method = self.method.get()
        self.progress.set(0)
        self.status.set(f"Выполняется: {method}")
        self.apply_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")

        def progress(done, total):
            self.events.put(("progress", done * 100 / max(1, total)))

        def task():
            try:
                result = self.controller.process(method, parameters, progress)
                self.events.put(("done", result, method))
            except InterruptedError:
                self.events.put(("cancelled",))
            except Exception as error:
                self.events.put(("error", str(error)))

        self.worker = threading.Thread(target=task, daemon=True)
        self.worker.start()

    def _cancel(self):
        self.controller.cancel()
        self.status.set("Отмена обработки...")

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.progress.set(event[1])
                elif event[0] == "done":
                    result, elapsed, threshold = event[1]
                    self._show_buffer(result, self.result_label, False)
                    self._update_histograms(result)
                    detail = f", порог {threshold:.2f}" if threshold is not None else ""
                    self.status.set(f"{event[2]}: {elapsed:.3f} с{detail}")
                    self.progress.set(100)
                    self._set_idle()
                elif event[0] == "cancelled":
                    self.status.set("Обработка отменена")
                    self._set_idle()
                elif event[0] == "error":
                    messagebox.showerror("Ошибка обработки", event[1])
                    self.status.set("Ошибка обработки")
                    self._set_idle()
        except queue.Empty:
            pass
        self.root.after(80, self._poll_events)

    def _set_idle(self):
        self.apply_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def _show_buffer(self, buffer, label, original):
        image = buffer.to_image().convert("RGB")
        image.thumbnail((470, 420), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        label.configure(image=photo, text="")
        if original:
            self.original_photo = photo
        else:
            self.result_photo = photo

    def _update_histograms(self, result):
        source = self.controller.original
        self.histogram_before = source.histogram()
        self.histogram_after = result.histogram()
        original = source.to_image().convert("RGB").tobytes()
        processed = result.to_image().convert("RGB").tobytes()
        changed = sum(original[i:i + 3] != processed[i:i + 3] for i in range(0, len(original), 3))
        total = source.width * source.height
        self.histogram_summary.set(f"Изменено пикселей: {changed:,} из {total:,} ({changed * 100 / total:.3f}%). Красный: убыло, зелёный: прибыло; наведите курсор на график.")
        self._redraw_histograms()

    def _redraw_histograms(self):
        if self.histogram_before is None:
            return
        peak = max(1, max(self.histogram_before), max(self.histogram_after))
        self._draw_histogram(self.original_hist, self.histogram_before, "#3568a8", peak)
        self._draw_histogram(self.result_hist, self.histogram_after, "#2a9d8f", peak)
        canvas = self.difference_hist
        canvas.delete("all")
        width, height = max(100, canvas.winfo_width()), max(50, canvas.winfo_height())
        left, right = 65, width - 12
        middle = (height - 16) / 2
        delta = [after - before for before, after in zip(self.histogram_before, self.histogram_after)]
        scale = max(1, max(abs(value) for value in delta))
        amplitude = max(5, middle - 12)
        canvas.create_line(left, middle, right, middle, fill="#8290a0")
        canvas.create_text(4, 3, text=f"+{scale:,}", anchor="nw", fill="#16825e")
        canvas.create_text(4, middle, text="0", anchor="w", fill="#54606e")
        canvas.create_text(4, height - 18, text=f"−{scale:,}", anchor="sw", fill="#c24b43")
        for level, amount in enumerate(delta):
            if amount:
                x1 = left + level * (right - left) / 256
                x2 = left + (level + 1) * (right - left) / 256
                y = middle - amount * amplitude / scale
                color = "#16825e" if amount > 0 else "#c24b43"
                canvas.create_rectangle(x1, min(y, middle), x2, max(y, middle), fill=color, outline=color)
        if not any(delta):
            canvas.create_text((left + right) / 2, 12, text="Распределение яркости не изменилось", fill="#54606e")
        canvas.create_text(left, height - 2, text="0", anchor="sw", fill="#54606e")
        canvas.create_text(right, height - 2, text="255", anchor="se", fill="#54606e")
        canvas.bind("<Motion>", self._histogram_hover)
        canvas.bind("<Leave>", lambda event: canvas.delete("hover"))

    def _histogram_hover(self, event):
        canvas = self.difference_hist
        canvas.delete("hover")
        width = max(100, canvas.winfo_width())
        level = min(255, max(0, int((event.x - 65) * 256 / max(1, width - 77))))
        before, after = self.histogram_before[level], self.histogram_after[level]
        canvas.create_text(width / 2, 3, text=f"Яркость {level}: до {before:,}, после {after:,}, разница {after - before:+,}", anchor="n", fill="#183153", tags="hover")

    def _draw_histogram(self, canvas, histogram, color, peak=None):
        canvas.delete("all")
        width = max(100, canvas.winfo_width())
        height = max(50, canvas.winfo_height())
        peak = max(1, peak if peak is not None else max(histogram, default=1))
        left, right = 65, width - 12
        baseline = height - 20
        canvas.create_text(4, 3, text=f"{peak:,}", anchor="nw", fill="#54606e")
        canvas.create_line(left, 8, left, baseline, right, baseline, fill="#8290a0")
        for level, amount in enumerate(histogram):
            if amount:
                x1 = left + level * (right - left) / 256
                x2 = left + (level + 1) * (right - left) / 256
                bar = amount * (baseline - 8) / peak
                canvas.create_rectangle(x1, baseline - bar, x2, baseline, fill=color, outline=color)
        canvas.create_text(left, height - 2, text="0", anchor="sw", fill="#54606e")
        canvas.create_text(right, height - 2, text="255", anchor="se", fill="#54606e")

    def run(self):
        self.root.mainloop()
