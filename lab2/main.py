import ctypes

from infrastructure.parsers import parse_image
from presentation.ui import ImageInspectorApp


if __name__ == "__main__":
    app = ImageInspectorApp(parse_image)
    console = ctypes.windll.kernel32.GetConsoleWindow()
    if console:
        ctypes.windll.user32.ShowWindow(console, 0)
    app.mainloop()

