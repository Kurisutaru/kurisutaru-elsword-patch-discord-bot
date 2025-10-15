import os
import random
import re
import sys
import zipfile
from datetime import datetime

from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from discord_webhook import DiscordWebhook, DiscordEmbed
from loguru import logger as log

import requests
from environs import env

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

env.read_env()

# Configure logging
# Configure log
log_file = os.path.join(script_dir, 'app.log')
log.remove()
log_format = ("<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
              "<level>{level: <8}</level> | "
              "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")


# Because I hate they're adding the hh:mm:ss SSS something to the filename
# And I only need the date they rotate the file itself
def kuri_zip_compression(file_path):
    """Simple compression with current date"""
    directory = os.path.dirname(file_path) or "."
    today = datetime.now().strftime("%Y-%m-%d")

    log_dir = os.path.join(directory, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    zip_filename = os.path.join(log_dir, f"app.{today}.log.zip")

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, f"app.{today}.log")

    os.remove(file_path)


log.add(sys.stdout,
        format=log_format,
        colorize=True,
        )

log.add(
    log_file,
    rotation="sunday",
    compression=kuri_zip_compression,
    encoding="utf-8",
    level="INFO",
    format=log_format
)

# Define the paths and URLs
VERSION_FILE = os.path.join(script_dir, 'version')
PATCH_PATH_URL = 'http://elsword-jp.dn.playkog.com/LIVE/PatchPath_64.dat'
PATCHINFO_DIR = os.path.join(script_dir, 'patchinfo')
DISCORD_WEBHOOK_URL = env('DISCORD_WEBHOOK_URL')

# Usual Socks5 proxy if you don't have proxy set to None
override_proxy = env.bool('OVERRIDE_PROXY')
proxy_config = env('PROXY_CONFIG')

KOM_LIST = [
    # Char Skill SFX
    "data069.kom",
    # Tutorial Misc
    "data081.kom",
    # NPC Voice
    "data096.kom",
    # Boss Voice
    "data104.kom",
    # Elsword
    "data080.kom",
    "data093.kom",
    "data174.kom",
    # Aisha
    "data079.kom",
    "data092.kom",
    "data168.kom",
    # Rena
    "data083.kom",
    "data095.kom",
    "data176.kom",
    # Raven
    "data084.kom",
    "data097.kom",
    "data178.kom",
    # Eve
    "data082.kom",
    "data094.kom",
    "data175.kom",
    # Chung
    "data108.kom",
    "data109.kom",
    "data171.kom",
    # Ara
    "data133.kom",
    "data134.kom",
    "data169.kom",
    "data170.kom",
    # Elesis
    "data144.kom",
    "data145.kom",
    "data173.kom",
    # Add
    "data149.kom",
    "data150.kom",
    "data167.kom",
    # Lu
    "data160.kom",
    "data162.kom",
    "data177.kom",
    # Ciel
    "data161.kom",
    "data163.kom",
    "data172.kom",
    # Roze
    "data186.kom",
    "data187.kom",
    "data188.kom",
    # Ain
    "data210.kom",
    "data213.kom",
    "data214.kom",
    # Laby
    "data251.kom",
    "data253.kom",
    # Noah
    "data281.kom",
    "data282.kom",
    "data283.kom",
    # Lithia
    "data321.kom",
    "data328.kom",
]


def get_local_version():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'w') as f:
            f.write('0.0.0')  # Initialize with a default version number
    with open(VERSION_FILE, 'r') as f:
        return f.read().strip()


def get_previous_patchinfo_file(local_version):
    if not os.path.exists(PATCHINFO_DIR):
        return None
    patchinfo_file = os.path.join(PATCHINFO_DIR, f'patchinfo-{local_version}.xml')
    return patchinfo_file if os.path.exists(patchinfo_file) else None


def get_remote_version_and_url():
    proxy = {"http": proxy_config, "https": proxy_config} if override_proxy else {}
    response = requests.get(url=PATCH_PATH_URL, proxies=proxy)
    response.raise_for_status()  # Ensure we have a successful request

    # Extract the URL from the text within brackets
    url_match = re.search(r'<(http://[^\s>]+)>', response.text)
    if not url_match:
        raise ValueError("Failed to find URL in the response")

    patch_url = url_match.group(1)

    # Extract the filename and version from the URL
    filename_match = re.search(r'/([^/]+)/$', patch_url)
    if not filename_match:
        raise ValueError("Failed to parse filename from the URL")

    patch_version_raw = filename_match.group(1)

    # Extract the version from the filename
    version_match = re.search(r'_(\d.+)', patch_version_raw)
    if not version_match:
        raise ValueError("Failed to parse version from the filename")

    patch_version = version_match.group(1)

    # Construct the patch_info_url
    patch_info_url = urljoin(patch_url, "patchinfo.xml")

    return patch_url, patch_version_raw, patch_version, patch_info_url


def download_patchinfo(patch_info_url, patch_version):
    proxy = {"http": proxy_config, "https": proxy_config} if override_proxy else {}
    response = requests.get(url=patch_info_url, proxies=proxy)
    response.raise_for_status()  # Ensure we have a successful request

    # Create patchinfo directory if it doesn't exist
    os.makedirs(PATCHINFO_DIR, exist_ok=True)

    # Save the patchinfo.xml with version in filename
    patchinfo_path = os.path.join(PATCHINFO_DIR, f'patchinfo-{patch_version}.xml')
    with open(patchinfo_path, 'wb') as f:
        f.write(response.content)

    return patchinfo_path


def load_patchinfo(patchinfo_path):
    with open(patchinfo_path, 'r', encoding='utf-8') as f:
        return ET.parse(f).getroot()


def compare_patchinfo_kom_files(current_patchinfo, previous_patchinfo_path):
    if not previous_patchinfo_path or not os.path.exists(previous_patchinfo_path):
        return []

    previous_patchinfo = load_patchinfo(previous_patchinfo_path)
    differences = []

    # Prepend 'data/' to file names when creating dictionaries
    current_files = {f"{file.get('Name')}": file.get('Checksum') for file in current_patchinfo.findall('.//File')}
    previous_files = {f"{file.get('Name')}": file.get('Checksum') for file in
                      previous_patchinfo.findall('.//File')}

    for kom_file in KOM_LIST:
        # Prepend 'data/' to match the format in patchinfo.xml
        kom_file_with_path = f"data\\{kom_file}"
        current_checksum = current_files.get(kom_file_with_path)
        previous_checksum = previous_files.get(kom_file_with_path)

        if current_checksum and previous_checksum and current_checksum != previous_checksum:
            # differences.append(f"{kom_file}: Checksum changed from {previous_checksum} to {current_checksum}")
            differences.append(f"{kom_file}")

    return differences


def get_random_hex_color():
    # Generate a random integer between 0 and 0xFFFFFF
    random_color = random.randint(0, 0xFFFFFF)
    return random_color


def send_discord_embed(patch_url, patch_version_raw, patch_version, patch_info_url, differences):
    # Create the main patch update embed
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL)

    header_embed = DiscordEmbed(title="Elsword Japan - Patch Update",
                         description="A new patch is available for Elsword Japan.",
                         color=get_random_hex_color())
    header_embed.add_embed_field(name="Patch Version", value=patch_version, inline=False)
    header_embed.add_embed_field(name="Patch Version Raw", value=patch_version_raw, inline=False)
    header_embed.add_embed_field(name="Patch URL", value=f"||[Patch URL]({patch_url})||", inline=False)
    header_embed.add_embed_field(name="Patch Info URL", value=f"||[Patch Info URL]({patch_info_url})||", inline=False)

    # Create the KOM changes embed, always included
    kom_value = "No File Changes" if not differences else "```\n" + "\n".join(differences) + "\n```"
    kom_embed = DiscordEmbed(title="Elsword Japan - Voice KOM File Changes",
                         description="Voice KOM file status for the new patch.",
                         color=get_random_hex_color())
    kom_embed.add_embed_field(name="Changed Voice Files", value=kom_value, inline=False)

    webhook.add_embed(header_embed)
    webhook.add_embed(kom_embed)

    if override_proxy:
        proxies = {"http": proxy_config, "https": proxy_config}
        webhook.set_proxies(proxies)

    response = webhook.execute()
    if response.ok:
        log.info("Embeds sent successfully.")
    else:
        log.error(f"Failed to send embeds. HTTP Response Code: {response.status_code}")


def main():
    local_version = get_local_version()
    try:
        patch_url, patch_version_raw, patch_version, patch_info_url = get_remote_version_and_url()
    except Exception as e:
        log.error(f"Error fetching remote version: {e}")
        return

    if local_version != patch_version:
        log.info(f"New patch available. Local version: {local_version}, Remote version: {patch_version}")

        # Download and save patchinfo.xml
        patchinfo_path = download_patchinfo(patch_info_url, patch_version)

        # Load the current patchinfo
        current_patchinfo = load_patchinfo(patchinfo_path)

        # Get the previous patchinfo file using the local version
        previous_patchinfo_file = get_previous_patchinfo_file(local_version)

        # Compare KOM files
        differences = compare_patchinfo_kom_files(current_patchinfo, previous_patchinfo_file)

        # Send Discord embeds
        send_discord_embed(patch_url, patch_version_raw, patch_version, patch_info_url, differences)

        # Update local version file
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            f.write(patch_version)

        log.info(f"PATCH_URL: {patch_url}")
        log.info(f"PATCH_INFO_URL: {patch_info_url}")
        log.info(f"PATCH_VERSION_RAW: {patch_version_raw}")
        log.info(f"PATCH_VERSION: {patch_version}")
    else:
        log.info("Versions are the same. No update needed.")


if __name__ == '__main__':
    main()
