from core.bootstrap import build_executor

from tui_app import MyCLIApp


def main():
    executor = build_executor()

    app = MyCLIApp(executor)
    app.run()


if __name__ == "__main__":
    main()