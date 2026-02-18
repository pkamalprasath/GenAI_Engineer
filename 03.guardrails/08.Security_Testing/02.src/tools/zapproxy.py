import os
from crewai.tools import tool
import subprocess


@tool("ZAPGeneralUse")
def zap_general_use(
    website: str) -> str:
    """ Penn Testing on website using ZapProxy Tool
    Parameters: None

    Returns:
    - str: The results of the ZAP operation or an error message.
    """
    os.chdir(r"C:\Program Files\ZAP\Zed Attack Proxy")
    base_command = f"\"C:\Program Files\ZAP\Zed Attack Proxy\zap.bat\" -quickurl {website} -quickprogress -cmd"

    print(f"Running Zaproxy command: {base_command}")

    # Execute the command using subprocess
    process = subprocess.Popen(
        base_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception(f"Error executing ZAP: {stderr.decode('utf-8')}")

    return stdout.decode("utf-8")


# java -Xmx512m -jar zap-2.16.1.jar -quickurl http://www.hackthissite.org -cmd