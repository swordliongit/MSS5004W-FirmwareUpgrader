import os
import subprocess
import sys
from time import sleep
import customtkinter

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.alert import Alert

from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from configparser import ConfigParser


DEBUG = True
TIMEOUT = 20
CURRENT_MAC = ""
current_dir = os.path.dirname(__file__)
IMAGE_LOCATION = os.path.join(current_dir, "firmware")
mac_list = []

config = ConfigParser()
config.read(os.path.join(current_dir, "config.ini"))


def login(Console, driver):
    url = config.get("luci", "url")
    username = config.get("luci", "username")
    password = config.get("luci", "password")
    if DEBUG:
        print(IMAGE_LOCATION, url, username, password)

    try:
        driver.get(url)  # open the url
        driver.find_element(By.ID, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.ID, "login_in").click()  # login button
        sleep(0.5)
        return True
    except:
        WriteToConsole(Console, "<< Login failed! >>\n")


def crawl(Console, driver):
    global CURRENT_MAC
    global IMAGE_LOCATION
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "LAN Information"))
        ).click()
        sleep(3)
        CURRENT_MAC = (
            WebDriverWait(driver, 10)
            .until(EC.presence_of_element_located((By.CSS_SELECTOR, "#ra0-ifc-mac")))
            .text
        )
        if CURRENT_MAC in mac_list:
            raise Exception("Upgrade aborted: Duplicate modem found!")
        else:
            mac_list.append(CURRENT_MAC)
        WriteToConsole(Console, f"Login: {CURRENT_MAC}\n")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "System"))
        ).click()
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Backup / Flash Firmware"))
        ).click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#keep"))
        ).click()
        image_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#image"))
        )
        image_button.send_keys(IMAGE_LOCATION)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "#maincontent > div > div:nth-child(5) > div > div > form > div:nth-child(2) > div > div > input.cbi-button.cbi-input-apply",
                )
            )
        ).click()
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "#maincontent > div > div:nth-child(2) > div:nth-child(3) > form:nth-child(2) > input.cbi-button.cbi-button-apply",
                )
            )
        ).click()
        # driver.close()
    except Exception as e:
        return False, e.__class__.__name__, str(e)
    else:
        return True, None, None


def logged_out(Console, driver):
    try:
        driver.find_element(By.ID, "login_in")
    except:
        return False
    else:
        return True


def get_device_mac():
    try:
        arp_output = subprocess.check_output(
            "arp -a", shell=True, universal_newlines=True
        )
        lines = arp_output.strip().split("\n")
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 3:
                ip_address, mac_address, _ = parts
                if mac_address.startswith("1c-18-4a"):
                    return mac_address
    except subprocess.CalledProcessError as e:
        print(f"Error running 'arp -a': {e}")
    return None


def WriteToConsole(Console, text):
    Console.configure(state="normal")
    Console.insert(customtkinter.END, text)
    Console.configure(state="disabled")
    Console.see(customtkinter.END)  # Scroll to the end


def initiate(Console, driver, button, modem_count):
    """_summary_

    Args:
        Console (_type_): _description_
        entry_1 (_type_): _description_
    """
    global CURRENT_MAC
    global mac_list
    crawl_successful = False
    upgraded_count = 0

    WriteToConsole(Console, f"\n\nStarting...\n\n")

    # chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # silent browser
    # driver = webdriver.Chrome(options=chrome_options)
    # driver = webdriver.Chrome()

    WriteToConsole(Console, f"\n\nModem Count: {modem_count}\n\n")

    for _ in range(modem_count):
        if login(Console, driver):
            if not logged_out(Console, driver):
                crawl_successful, excpt, excpt_msg = crawl(Console, driver)
                if crawl_successful:
                    WriteToConsole(
                        Console, f"Firmware Upgrade Successful for: {CURRENT_MAC}\n"
                    )
                    upgraded_count += 1
                    if upgraded_count == modem_count:
                        break
                else:
                    WriteToConsole(
                        Console, f"<< Firmware Upgrade Failed for: {CURRENT_MAC} >>\n"
                    )
                    WriteToConsole(Console, f"Error type: {excpt}\n")
                    WriteToConsole(Console, f"Error msg: {excpt_msg}\n")
                    upgraded_count += 1
                    if upgraded_count == modem_count:
                        break
                    continue
        else:
            WriteToConsole(Console, "No modems found!\n\n")
            break
        WriteToConsole(Console, "Waiting for the next modem input...\n\n")
        sleep(70)
    WriteToConsole(
        Console, f"\n\n******Upgraded Modem Count: {upgraded_count}******\n\n"
    )
    button.configure(state="normal")
    mac_list.clear()
    driver.close()
