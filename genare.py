import os
import tkinter as tk

from genare_app import GenareApp


def main():
    compatible_api_url = os.getenv("GENARE_API_URL", "http://localhost:11434/v1")
    api_key = os.getenv("GENARE_API_KEY", "sk-no-key-needed")
    model_name = os.getenv("GENARE_MODEL", "gemma4:e4b")

    root = tk.Tk()
    GenareApp(root, base_url=compatible_api_url, api_key=api_key, model=model_name)
    root.mainloop()


if __name__ == "__main__":
    main()
