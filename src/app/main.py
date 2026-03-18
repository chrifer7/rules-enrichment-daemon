from app.interfaces.cli.main import app


def main() -> None:
    # Keep the package entry point intentionally tiny.
    # The actual commands live in the interfaces layer so packaging concerns
    # do not leak into business/application code.
    app()


if __name__ == "__main__":
    main()
