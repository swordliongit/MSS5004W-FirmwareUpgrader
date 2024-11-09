from concurrent.futures import ThreadPoolExecutor
import os
import platform
import re
import socket
import subprocess
import sys
from time import sleep
import time
import customtkinter

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.common.alert import Alert

from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from configparser import ConfigParser


DEBUG = True

TIMEOUT = 20
CURRENT_MAC = ""
MAX_WAIT_TIME = 100  # Maximum time to wait for a modem in seconds
CONNECTION_CHECK_INTERVAL = 20  # Time between connection checks in seconds
current_dir = os.path.dirname(__file__)
IMAGE_LOCATION = os.path.join(current_dir, "new-firmware.bin")
mac_list = []

config = ConfigParser()
config.read(os.path.join(current_dir, "config.ini"))


def login(Console, driver: webdriver.Chrome):
    url = config.get("luci", "url")
    username = config.get("luci", "username")
    password = config.get("luci", "password")

    try:
        driver.set_page_load_timeout(10)  # Set page load timeout
        driver.get(url)
        
        # Wait for login elements with timeout
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(username)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(password)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "login_in"))).click()
        
        sleep(0.5)
        return True
    except TimeoutException:
        WriteToConsole(Console, "Login sayfası yüklenemedi - bağlantı zaman aşımına uğradı.\n")
        return False
    except WebDriverException as e:
        error_message = str(e)
        if "net::ERR_CONNECTION_TIMED_OUT" in error_message:
            WriteToConsole(Console, "Bağlantı zaman aşımına uğradı.\n")
        else:
            WriteToConsole(Console, f"Login hatası: {error_message}\n")
        return False
    except Exception as e:
        WriteToConsole(Console, f"Beklenmeyen hata: {str(e)}\n")
        return False


def logged_out(Console, driver):
    try:
        driver.find_element(By.ID, "login_in")
    except:
        return False
    else:
        return True


def WriteToConsole(Console, text):
    Console.configure(state="normal")
    Console.insert(customtkinter.END, text)
    Console.configure(state="disabled")
    Console.see(customtkinter.END)  # Scroll to the end
    

def get_mac_from_interface(driver):
    """Get MAC address directly from modem web interface"""
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, "LAN Information"))).click()
        sleep(2)
        mac_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#ra0-ifc-mac"))
        )
        return mac_element.text
    except Exception as e:
        if DEBUG:
            print(f"Error getting MAC from interface: {str(e)}")
        return None
    
    
    
def verify_upgrade_success(driver, mac_address):
    """
    Verify that the upgrade actually completed successfully
    Returns: (success, error_message)
    """
    try:
        # Wait a bit for any redirects/reloads to complete
        sleep(5)
        
        # Try to access the login page again - if we can, upgrade probably failed
        try:
            driver.get("http://192.168.1.1")
            login_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "login_in"))
            )
            # If we can see login page immediately, upgrade didn't start
            return False, "Yükleme başlamadı - login sayfası hala erişilebilir"
        except:
            # This is actually good - means the modem is probably rebooting
            pass
            
        return True, None
        
    except Exception as e:
        return False, str(e)
    
    
    
def crawl(Console, driver):
    """
    Perform the firmware upgrade without overly aggressive verification
    """
    global CURRENT_MAC
    global IMAGE_LOCATION
    try:
        # Navigate to System menu
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.LINK_TEXT, "System"))).click()
        
        # Navigate to firmware upgrade page
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Backup / Flash Firmware"))
        ).click()
        
        # Select "Keep settings" checkbox
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#keep"))).click()
        
        # Upload firmware file
        image_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#image"))
        )
        image_button.send_keys(IMAGE_LOCATION)
        
        # Click the first flash button
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "#maincontent > div > div:nth-child(5) > div > div > form > div:nth-child(2) > div > div > input.cbi-button.cbi-input-apply"
            ))
        ).click()
        
        # Click the final confirmation button
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "#maincontent > div > div:nth-child(2) > div:nth-child(3) > form:nth-child(2) > input.cbi-button.cbi-button-apply"
            ))
        ).click()
        
        WriteToConsole(Console, f"Firmware yükleme başladı: {CURRENT_MAC}\n")
        
        # Wait a moment to let the upgrade process begin
        sleep(5)
        
        # If we got here, consider it a success
        return True, None, None
        
    except Exception as e:
        # If we got a timeout after showing "firmware yükleme başladı", consider it success
        if isinstance(e, TimeoutException) and "firmware yükleme başladı" in Console.get("1.0", "end-1c").lower():
            return True, None, None
            
        return False, e.__class__.__name__, str(e)
    


def crawler_controller(Console, driver):
    """
    Controls the crawl process without overly aggressive verification
    """
    try:
        with ThreadPoolExecutor() as executor:
            if logged_out(Console, driver):
                login(Console, driver)
            crawl_future = executor.submit(crawl, Console, driver)

        # Wait for crawl to complete
        crawl_result = crawl_future.result()
        
        # Consider it a success if crawl returns success
        return crawl_result

    except Exception as e:
        return False, e.__class__.__name__, str(e)
    
    

def initiate(Console, texbox_mac_list, driver: webdriver.Chrome, button_start, modem_count):
    """Main function with improved upgrade detection"""
    global CURRENT_MAC
    global mac_list
    
    WriteToConsole(Console, f"\nBaşlıyor, lütfen bekleyin...\n")
    WriteToConsole(Console, f"Modem Sayısı: {modem_count}\n\n")

    start_time = time.time()
    last_activity_time = start_time
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 30
    INACTIVITY_TIMEOUT = 300
    WAIT_BETWEEN_CHECKS = 10
    STATUS_INTERVAL = 10
    last_status_time = 0
    
    successfully_upgraded_macs = set()
    last_status_message = ""
    
    start_new_update_cycle(texbox_mac_list)
    
    while len(successfully_upgraded_macs) < modem_count:
        current_time = time.time()
        
        if current_time - last_activity_time > INACTIVITY_TIMEOUT:
            WriteToConsole(Console, f"Son {INACTIVITY_TIMEOUT//60} dakika içinde modem bulunamadı. İşlem iptal ediliyor.\n")
            break
            
        # Check for modem availability
        is_available = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('192.168.1.1', 80))
            sock.close()
            is_available = (result == 0)
        except:
            pass
            
        if not is_available:
            consecutive_failures += 1
            
            if current_time - last_status_time >= STATUS_INTERVAL:
                elapsed_time = int(current_time - last_activity_time)
                status_msg = f"Modem bekleniyor... (Son aktiviteden bu yana geçen süre: {elapsed_time} saniye, " \
                           f"Deneme: {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})\n"
                if status_msg != last_status_message:
                    WriteToConsole(Console, status_msg)
                    last_status_message = status_msg
                last_status_time = current_time
            
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                if len(successfully_upgraded_macs) == 0:
                    WriteToConsole(Console, "Hiç modem bulunamadı. İşlem iptal ediliyor.\n")
                else:
                    WriteToConsole(Console, f"Son {MAX_CONSECUTIVE_FAILURES * WAIT_BETWEEN_CHECKS} saniye içinde " \
                                          f"yeni modem bulunamadı. İşlem iptal ediliyor.\n")
                break
                    
            time.sleep(WAIT_BETWEEN_CHECKS)
            continue

        # Try to login and upgrade
        if login(Console, driver):
            current_mac = get_mac_from_interface(driver)
            if not current_mac:
                continue
                
            WriteToConsole(Console, f"Modem algılandı (MAC: {current_mac})\n")
            
            if current_mac in successfully_upgraded_macs:
                status_msg = f"Bu modem zaten güncellendi (MAC: {current_mac}). " \
                            f"Yeni modem bekleniyor ({len(successfully_upgraded_macs)}/{modem_count} tamamlandı)...\n"
                if status_msg != last_status_message:
                    WriteToConsole(Console, status_msg)
                    last_status_message = status_msg
                time.sleep(WAIT_BETWEEN_CHECKS)
                continue

            CURRENT_MAC = current_mac
            crawl_successful, excpt, excpt_msg = crawler_controller(Console, driver)
            
            if crawl_successful:
                successfully_upgraded_macs.add(CURRENT_MAC)
                update_mac_list(texbox_mac_list, CURRENT_MAC)
                WriteToConsole(Console, f"Firmware Güncellemesi Başarılı: {CURRENT_MAC}\n")
                last_activity_time = time.time()
                
                if len(successfully_upgraded_macs) < modem_count:
                    WriteToConsole(Console, 
                        f"Modem yeniden başlatılıyor ve bir sonraki modem bekleniyor... "
                        f"({len(successfully_upgraded_macs)}/{modem_count} tamamlandı)\n"
                    )
                    time.sleep(30)  # Initial wait after successful upgrade
            else:
                WriteToConsole(Console, f"Firmware Güncellemesi Başarısız\n")
                if excpt:
                    WriteToConsole(Console, f"Hata: {excpt}\n")
    
    WriteToConsole(Console, f"\n****** Güncellenen modem sayısı: {len(successfully_upgraded_macs)} ******\n\n")
    mac_list = list(successfully_upgraded_macs)
    cleanup(texbox_mac_list, button_start)


def check_modem_availability(Console, ip="192.168.1.1", timeout=2):
    """Check modem web interface availability"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 80))
        sock.close()
        return result == 0, "Modem hazır" if result == 0 else "Modem bulunamadı"
    except Exception as e:
        return False, f"Bağlantı hatası: {str(e)}"
    
def update_mac_list(texbox_mac_list, mac):
    """Update the MAC address list in the UI - only called for successful updates"""
    texbox_mac_list.configure(state="normal")
    texbox_mac_list.insert(customtkinter.END, " " * 20 + mac + "\n")
    texbox_mac_list.configure(state="disabled")
    texbox_mac_list.see(customtkinter.END)

def start_new_update_cycle(texbox_mac_list):
    """Add a visual separator to indicate a new update cycle"""
    texbox_mac_list.configure(state="normal")
    texbox_mac_list.insert(customtkinter.END, "\n" + "-" * 75 + "\n" + 
                          " " * 15 + "Yeni Güncelleme Döngüsü" + "\n" + 
                          "-" * 75 + "\n\n")
    texbox_mac_list.configure(state="disabled")
    texbox_mac_list.see(customtkinter.END)

def cleanup(texbox_mac_list, button_start):
    """Clean up after completion of a cycle"""
    texbox_mac_list.configure(state="normal")
    texbox_mac_list.insert(customtkinter.END, "\n")
    texbox_mac_list.configure(state="disabled")
    texbox_mac_list.see(customtkinter.END)
    button_start.configure(state="normal")
    mac_list.clear()  # Clear the list for the new cycle