from concurrent.futures import ThreadPoolExecutor
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
IMAGE_LOCATION = os.path.join(current_dir, "new-firmware.bin")
mac_list = []

config = ConfigParser()
config.read(os.path.join(current_dir, "config.ini"))


def login(Console, driver: webdriver.Chrome):
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
    except WebDriverException as e:
        error_message = str(e)
        if "net::ERR_CONNECTION_TIMED_OUT" in error_message:
            # Handle connection timeout
            WriteToConsole(
                Console,
                f"<< Login failed! >>\nException: {e.__class__.__name__}\nMessage: Connection timed out.\n",
            )
        else:
            # Handle other WebDriverExceptions
            WriteToConsole(
                Console,
                f"<< Login failed! >>\nException: {e.__class__.__name__}\nMessage:{error_message}\n",
            )
        return False
    except Exception as e:
        # Handle other exceptions
        WriteToConsole(
            Console,
            f"<< Login failed! >>\nException: {e.__class__.__name__}\nMessage:{str(e)}\n",
        )
        return False


def crawl(Console, driver):
    global CURRENT_MAC
    global IMAGE_LOCATION
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, "LAN Information"))).click()
        sleep(3)
        CURRENT_MAC = (
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#ra0-ifc-mac"))).text
        )
        if CURRENT_MAC in mac_list:
            raise Exception("Upgrade aborted: Duplicate modem found!")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, "System"))).click()
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Backup / Flash Firmware"))
        ).click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#keep"))).click()
        image_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#image")))
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
        WriteToConsole(Console, f"Login: {CURRENT_MAC}\n")
        mac_list.append(CURRENT_MAC)
    except Exception as e:
        return False, e.__class__.__name__, str(e)
    else:
        return True, None, None


def crawler_controller(Console, driver):
    try:
        # Execute crawl function in a separate thread
        with ThreadPoolExecutor() as executor:
            if logged_out(Console, driver):
                login(Console, driver)
            crawl_future = executor.submit(crawl, Console, driver)

        # Use a loop to repeatedly check for logged-out status while crawl is in progress
        while not crawl_future.done():
            # Execute logged_out function in a separate thread
            with ThreadPoolExecutor() as executor:
                logged_out_future = executor.submit(logged_out, Console, driver)

            # Wait for the logged_out thread to complete
            logged_out_result = logged_out_future.result()

            # Check if logged out and restart the crawl
            if logged_out_result:
                crawl_future.cancel()  # Cancel the ongoing crawl
                return crawler_controller(Console, driver)
            sleep(3)

        # Wait for the crawl to complete and get the result
        crawl_result = crawl_future.result()

        # Check for logged-out status after crawl completion
        logged_out_result = logged_out(Console, driver)

        # Check if logged out and restart the crawl
        if logged_out_result:
            return crawler_controller(Console, driver)

        # Return crawl result
        return crawl_result

    except Exception as e:
        return False, e.__class__.__name__, str(e)


def logged_out(Console, driver):
    try:
        driver.find_element(By.ID, "login_in")
    except:
        return False
    else:
        return True


def get_device_mac():
    try:
        arp_output = subprocess.check_output("arp -a", shell=True, universal_newlines=True)
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


def ping_router(router_ip):
    try:
        # Run the ping command
        result = subprocess.run(['ping', router_ip, '-n', '1'], capture_output=True, text=True, timeout=5)
        # Check the return code
        if result.returncode == 0:
            # The ping was successful
            return True
        else:
            # The ping failed
            return False
    except subprocess.TimeoutExpired:
        # Handle the case where the ping times out
        return False


def WriteToConsole(Console, text):
    Console.configure(state="normal")
    Console.insert(customtkinter.END, text)
    Console.configure(state="disabled")
    Console.see(customtkinter.END)  # Scroll to the end


def initiate(Console, texbox_mac_list, driver: webdriver.Chrome, button_start, button_update, modem_count):
    """_summary_

    Args:
        Console (_type_): _description_
        entry_1 (_type_): _description_
    """
    global CURRENT_MAC
    global mac_list
    crawl_successful = False

    WriteToConsole(Console, f"\n\nBaşlıyor, lütfen bekleyin...\n")

    # chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")  # silent browser
    # driver = webdriver.Chrome(options=chrome_options)
    # driver = webdriver.Chrome()

    WriteToConsole(Console, f"Modem Sayısı: {modem_count}\n\n")

    max_connection_delay = 100
    previous_attempt = False

    while not modem_count == len(mac_list):
        if login(Console, driver):
            if not logged_out(Console, driver):
                previous_attempt = True
                crawl_successful, excpt, excpt_msg = crawler_controller(Console, driver)
                if crawl_successful:
                    WriteToConsole(Console, f"Firmware Güncellemesi Başarılı: {CURRENT_MAC}\n")
                    texbox_mac_list.configure(state="normal")
                    texbox_mac_list.insert(customtkinter.END, " " * 20 + CURRENT_MAC + "\n")
                    texbox_mac_list.configure(state="disabled")
                    texbox_mac_list.see(customtkinter.END)  # Scroll to the end
                else:
                    WriteToConsole(Console, f"<< Firmware Güncellemesi Başarısız: {CURRENT_MAC} >>\n")
                    WriteToConsole(Console, f"Error type: {excpt}\n")
                    # WriteToConsole(Console, f"Error msg: {excpt_msg}\n")
                    if len(mac_list) == modem_count:
                        break
                    continue
        else:
            WriteToConsole(Console, "Herhangi bir modem bulunamadı!\n\n")
            previous_attempt = False
        if not len(mac_list) == 0 and len(mac_list) != modem_count:
            WriteToConsole(Console, "Bir sonraki modemin bağlanması için bekleyin...\n\n")
            sleep(5)
        if previous_attempt and len(mac_list) != modem_count:
            while True:
                try:
                    driver.get(config.get("luci", "url"))
                except:
                    pass
                if logged_out(Console, driver):
                    break
                sleep(3)
    WriteToConsole(Console, f"\n******Güncellenen modem sayısı: {len(mac_list)}******\n\n")
    texbox_mac_list.configure(state="normal")
    texbox_mac_list.insert(customtkinter.END, "\n\n")
    texbox_mac_list.configure(state="disabled")
    texbox_mac_list.see(customtkinter.END)  # Scroll to the end
    button_start.configure(state="normal")
    button_update.configure(state="normal")
    mac_list.clear()
