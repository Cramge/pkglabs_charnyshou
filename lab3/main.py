import multiprocessing

from presentation.ui import ImageProcessingApp


def main():
    app = ImageProcessingApp()
    app.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
