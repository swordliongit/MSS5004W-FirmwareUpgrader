import platform
import re
import tkinter
import tkinter.messagebox
from tkinter.messagebox import showinfo

from configparser import ConfigParser
from threading import Thread
from time import sleep
import customtkinter as ctk
import json
import os
from crawler import initiate

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

import requests
import ctypes, sys

CURRENT_DIR = os.path.dirname(__file__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme(os.path.join(CURRENT_DIR, "custom_theme.json"))

DEBUG = False


class MasterGui(ctk.CTk):
    # Driver setup
    driver = None

    def __init__(self):
        global CURRENT_DIR
        super().__init__()

        # MasterGui setup
        self.title("Firmware Upgrader v1.2.0")
        self.geometry(f"{950}x{600}")
        self.resizable(width=False, height=False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # self.after(201, lambda: self.iconbitmap(os.path.join(CURRENT_DIR, "FU.ico")))
        self.iconbitmap(os.path.join(CURRENT_DIR, "FU.ico"))

        self.grid_rowconfigure((0, 1, 2, 3), weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Frame 1 and Border Frame
        self.border_frame = ctk.CTkFrame(master=self)
        self.border_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsw")
        self.frame_1 = ctk.CTkFrame(master=self.border_frame)
        self.frame_1.grid(row=0, column=0, padx=20, pady=20, sticky="ns")

        self.ModemCountEntry = ctk.CTkEntry(master=self.frame_1, placeholder_text="Modem Sayısı")
        self.ModemCountEntry.grid(row=1, column=0, columnspan=3, padx=10, pady=10, sticky="ns")

        self.button_start = ctk.CTkButton(
            master=self.frame_1,
            command=self.initiate_action,
            text="Modemleri Güncelle",
        )
        self.button_start.grid(row=2, column=0, columnspan=3, pady=10, padx=10, sticky="ns")

        self.Console_label = ctk.CTkLabel(
            self.frame_1, text="Güncelleme Monitörü", anchor="w", font=("Roboto", 16)
        )
        self.Console_label.grid(row=3, column=0, columnspan=3, padx=0, pady=0, sticky="ns")
        self.Console = ctk.CTkTextbox(master=self.frame_1, width=500, height=380, font=("Cascadia Code", 14))
        self.Console.grid(row=4, column=0, columnspan=3, pady=10, padx=10, sticky="ns")
        # self.Console.insert(ctk.END, " " * 55 + "Güncelleme Logları" + "\n" + "-" * 142 + "\n\n")
        self.Console.configure(state="disabled")

        self.tabview = ctk.CTkTabview(self, width=300, height=650)
        self.tabview.grid(row=0, column=1, padx=5, pady=(0, 20), sticky="n")
        self.tabview.add("Ayarlar")
        self.tabview.add("Hakkında")
        self.tabview.tab("Ayarlar").grid_columnconfigure(0, weight=1)  # configure grid of individual tabs
        self.tabview.tab("Hakkında").grid_columnconfigure(0, weight=1)
        self.texbox_about = ctk.CTkTextbox(master=self.tabview.tab("Hakkında"), width=280, height=400)
        self.texbox_about.grid(row=0, column=0)
        with open(os.path.join(CURRENT_DIR, "about.txt"), 'r', encoding="utf-8") as f:
            self.texbox_about.insert(ctk.END, f.read())
        self.texbox_about.configure(state="disabled")

        self.Mac_list_label = ctk.CTkLabel(
            self.tabview.tab("Ayarlar"),
            text="Tamamlanmış Güncelleme Listesi",
            anchor="w",
            font=("Roboto", 16),
        )
        self.Mac_list_label.grid(row=1, column=0, columnspan=3, padx=0, pady=0, sticky="ns")
        self.texbox_mac_list = ctk.CTkTextbox(master=self.tabview.tab("Ayarlar"), width=280, height=490)
        self.texbox_mac_list.grid(row=2, column=0, pady=(10, 0))
        self.texbox_mac_list.configure(state="disabled")

        self.driver = None
        self.driver_initialized = False

    # def start_internet_check_thread(self):
    #     # Create a separate thread for checking internet connection
    #     internet_check_thread = Thread(target=self.check_internet_connection)
    #     # Set the thread as a daemon so that it will exit when the main program exits
    #     internet_check_thread.daemon = True
    #     # Start the thread
    #     internet_check_thread.start()

    # def check_internet_connection(self):
    #     global INTERNET_CONNECTED
    #     if DEBUG:
    #         print(INTERNET_CONNECTED)
    #     while True:
    #         try:
    #             # Try making a simple request to a known server
    #             response = requests.get("https://www.google.com", timeout=5)
    #             # If the request is successful, the internet is connected
    #             INTERNET_CONNECTED = True
    #         except requests.exceptions.RequestException:
    #             # If an exception occurs, the internet is not connected
    #             INTERNET_CONNECTED = False

    #         # Wait for a certain interval before checking again
    #         if DEBUG:
    #             print(INTERNET_CONNECTED)
    #         sleep(5)  # Adjust the interval as needed

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

    def init_driver(self):
        try:
            # Configure Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            # Add error logging
            if DEBUG:
                print(f"Python version: {sys.version}")
                print(f"Platform: {platform.platform()}")
                print(f"Architecture: {platform.architecture()}")

            # Use try-except to handle potential ChromeDriver installation issues
            try:
                installation = ChromeDriverManager().install()
                folder = os.path.dirname(installation)
                driver_path = os.path.join(folder, "chromedriver.exe")
                service = ChromeService(driver_path)
            except Exception as e:
                self.Console.configure(state="normal")
                self.Console.insert(ctk.END, f"\nChromeDriver yüklenirken hata oluştu: {str(e)}\n")
                self.Console.configure(state="disabled")
                self.Console.see(ctk.END)
                return False

            # Initialize the driver with explicit service
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver_initialized = True
            return True

        except Exception as e:
            self.Console.configure(state="normal")
            self.Console.insert(ctk.END, f"\nSürücü başlatılırken hata oluştu: {str(e)}\n")
            self.Console.configure(state="disabled")
            self.Console.see(ctk.END)
            return False

    def initiate_action(self):
        modem_count_input = self.ModemCountEntry.get()

        try:
            modem_count = int(modem_count_input)
            if modem_count < 1:
                raise ValueError("Modem sayısı 1 veya daha fazla olmak zorundadır!")
        except ValueError:
            self.Console.configure(state="normal")
            self.Console.insert(
                ctk.END,
                "\nGeçerli bir modem sayısı girin (pozitif tamsayı)!\n",
            )
            self.Console.see(ctk.END)
            self.Console.configure(state="disabled")
            return

        if not self.driver_initialized:
            if not self.init_driver():
                return  # Exit if driver initialization failed

        self.button_start.configure(state="disabled")
        main_thread = Thread(
            target=initiate,
            args=(
                self.Console,
                self.texbox_mac_list,
                self.driver,
                self.button_start,
                int(self.ModemCountEntry.get()),
            ),
        )
        main_thread.start()
        self.update_idletasks()


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    # # initate the gui
    # FU = MasterGui()
    # FU.start_internet_check_thread()
    # sleep(2)
    # FU.Update_Init()
    # start the gui
    # FU.mainloop()
    FU = MasterGui()
    FU.mainloop()
    # if is_admin():
    #     # initate the gui
    #     FU = MasterGui()
    #     # FU.start_internet_check_thread()
    #     sleep(2)
    #     # start the gui
    #     FU.mainloop()
    # else:
    #     # Re-run the program with admin rights
    #     ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
