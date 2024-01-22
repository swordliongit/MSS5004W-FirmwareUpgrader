import re
import tkinter
import tkinter.messagebox

from configparser import ConfigParser
import threading
from time import sleep
import customtkinter
import json
import os
from crawler import initiate

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("dark-blue")


class Gui(customtkinter.CTk):
    # Driver setup
    driver = None

    def __init__(self):
        super().__init__()

        # Gui setup
        self.title("Firmware Upgrader v1.0.0")
        self.geometry(f"{550}x{550}")
        self.resizable(width=False, height=False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        current_dir = os.path.dirname(__file__)
        self.after(201, lambda: self.iconbitmap(os.path.join(current_dir, "FU.ico")))

        self.frame_1 = customtkinter.CTkFrame(master=self)
        self.frame_1.pack(pady=20, padx=40, fill="both", expand=True)

        self.ModemCountEntry = customtkinter.CTkEntry(
            master=self.frame_1, placeholder_text="Modem Count"
        )
        self.ModemCountEntry.pack(pady=10, padx=10)

        self.button_1 = customtkinter.CTkButton(
            master=self.frame_1,
            command=self.initiate_action,
            text="Start Firmware Upgrades",
        )
        self.button_1.pack(pady=10, padx=10)

        self.Console = customtkinter.CTkTextbox(master=self.frame_1, width=500, height=500)
        self.Console.pack(pady=10, padx=10)

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()), options=options
        )

    def is_valid_number(input_str):
        # Define a regular expression pattern to match valid numbers
        # This pattern allows positive and negative numbers, and floating-point numbers
        number_pattern = r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$"

        # Use re.match to check if the input matches the number pattern
        return bool(re.match(number_pattern, input_str))

    def on_closing(self):
        """Called when you press the X button to close the program. Kills the GUI and the opened chromedriver threads"""
        if self.driver is not None:
            try:
                self.driver.close()
            except Exception as e:
                # Handle any exception that occurs when trying to close the driver
                print(f"Error while closing the driver: {e}")
            if self.driver.session_id:
                self.driver.quit()
        self.destroy()

    def initiate_action(self):
        modem_count_input = self.ModemCountEntry.get()

        try:
            modem_count = int(modem_count_input)
            if modem_count < 1:
                raise ValueError("Modem count must be greater than or equal to 1")
        except ValueError:
            # Handle the case where the input is not a valid number
            self.Console.configure(state="normal")
            self.Console.insert(
                customtkinter.END,
                "\n\nEnter a valid Modem Count (a positive integer)!\n\n",
            )
            self.Console.see(customtkinter.END)  # Scroll to the end
            self.Console.configure(state="disabled")
            return
        self.button_1.configure(state="disabled")
        main_thread = threading.Thread(
            target=initiate,
            args=(
                self.Console,
                self.driver,
                self.button_1,
                int(self.ModemCountEntry.get()),
            ),
        )
        main_thread.start()

    def dummy2(self):
        pass

    def dummy3(self):
        pass


if __name__ == "__main__":
    # initate the gui
    FUGui = Gui()
    # start the gui
    FUGui.mainloop()
