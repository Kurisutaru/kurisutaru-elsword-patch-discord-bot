# Kurisutaru Elsword Patch Discord Bot

Small utilities to check on Elsword Japan server if there's any patch and compare if there's change for voice files.
It's automatically posted into discord channel via discord webhook.


Required to Run below first
### .env File
Edit the necessary settings on .env file

DISCORD_WEBHOOK_URL is a must, proxy is optional.
### UV / pip
```bash
uv sync
```
or
```bash
pip install -r requirements.txt
```
### And run as usual
```bash
python main.py
```
