import json
import random
import string
import time
from datetime import datetime
from impacket.smbconnection import SMBConnection
from impacket.dcerpc.v5.rpcrt import DCERPCException
from impacket.dcerpc.v5 import samr, scmr
from impacket.dcerpc.v5.dcomrt import DCOMConnection
from impacket.dcerpc.v5.dcom.wmi import (
    IWbemLevel1Login,
    IWbemServices,
    CLSID_WMILevel1Login,
    IID_IWbemLevel1Login
)
from config import SMB_TIMEOUT, MAX_RETRIES, CACHE_FILE, PASSWORD_LENGTH, SPECIAL_CHARS


def generate_password():
    chars = string.ascii_letters + string.digits + SPECIAL_CHARS
    while True:
        pwd = ''.join(random.choice(chars) for _ in range(PASSWORD_LENGTH))
        if (any(c.islower() for c in pwd) and
            any(c.isupper() for c in pwd) and
            any(c.isdigit() for c in pwd) and
            any(c in SPECIAL_CHARS for c in pwd)):
            return pwd


def load_cache():
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def parse_credentials(text):
    import re
    
    patterns = [
        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([^\s]+)\s+([^\s,|;]+)',
        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[|\s,;]+([^\s,|;]+)[|\s,;]+([^\s,|;]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            for m in matches:
                ip, user, pwd = m[0], m[1], m[2]
                if '\\' in user:
                    domain, username = user.split('\\', 1)
                else:
                    domain, username = '', user
                return ip, domain, username, pwd
    return None


def change_password_via_samr(ip, domain, username, old_pass, new_pass):
    for attempt in range(MAX_RETRIES):
        try:
            smb = SMBConnection(ip, ip, sess_port=445, timeout=SMB_TIMEOUT)
            smb.login(username, old_pass, domain if domain else '')
            
            rpc = samr.SAMR(smb.get_file('IPC$'))
            handle = samr.hSamrConnect(rpc, f'\\\\{ip}')['ServerHandle']
            
            samr_domain = domain if domain else ip
            domain_handle = samr.hSamrLookupDomainInSamServer(rpc, handle, samr_domain)['DomainHandle']
            user_handle = samr.hSamrOpenUser(rpc, domain_handle, 0x0002, username)['UserHandle']
            
            samr.hSamrChangePasswordUser(rpc, user_handle, old_pass, new_pass)
            
            smb.logoff()
            return True, "Success (SAMR)"
            
        except DCERPCException as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"SAMR RPC error: {str(e)}"
            time.sleep(1)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"SAMR connection error: {str(e)}"
            time.sleep(1)
    return False, "SAMR max retries exceeded"


def change_password_via_wmi(ip, domain, username, old_pass, new_pass):
    for attempt in range(MAX_RETRIES):
        try:
            auth = f"{domain}\\{username}" if domain else username
            dcom = DCOMConnection(ip, auth, old_pass, "", oxidResolver=True, timeout=SMB_TIMEOUT)
            iInterface = dcom.CoCreateInstanceEx(CLSID_WMILevel1Login, IID_IWbemLevel1Login)
            iWbemLevel1Login = IWbemLevel1Login(iInterface)
            iWbemServices = iWbemLevel1Login.NTLMLogin("root\\cimv2", "", "")
            iWbemLevel1Login.RemRelease()
            
            cmd = f"net user {username} {new_pass}"
            result = iWbemServices.ExecMethod("Win32_Process", "Create", {"CommandLine": cmd})
            return_code = result[0]['ReturnValue']
            
            dcom.disconnect()
            
            if return_code == 0:
                return True, "Success (WMI)"
            else:
                return False, f"WMI command failed with code {return_code}"
                
        except DCERPCException as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"WMI RPC error: {str(e)}"
            time.sleep(1)
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return False, f"WMI error: {str(e)}"
            time.sleep(1)
    return False, "WMI max retries exceeded"


def change_password_via_smb(ip, domain, username, old_pass, new_pass):
    success, msg = change_password_via_samr(ip, domain, username, old_pass, new_pass)
    if success:
        return success, msg
    
    return change_password_via_wmi(ip, domain, username, old_pass, new_pass)


def process_rdp(ip, domain, username, old_pass):
    cache = load_cache()
    key = f"{ip}:{domain}\\{username}" if domain else f"{ip}:{username}"
    
    if key in cache:
        return False, "Already processed", None
    
    new_pass = generate_password()
    success, msg = change_password_via_smb(ip, domain, username, old_pass, new_pass)
    
    record = {
        "ip": ip,
        "domain": domain,
        "username": username,
        "old_password": old_pass,
        "new_password": new_pass if success else None,
        "status": "success" if success else "failed",
        "error": None if success else msg,
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }
    
    cache[key] = record
    save_cache(cache)
    
    return success, msg, record