# Simple twitter post downloader
## How it works
This code uses the new v2 api twitter uses, and it uses guest authentication to fetch information about the tweet from the graphql api. It gets the authorization bearer from a main.js file and generates a guest token from the official api.

Gifs are stored as mp4, you can convert it to gifs with ffmpeg.

Guest token expires, but bearer token doesn't, so its cached in a txt file to avoid unnecessary bandwidth.

Accepts x.com and twitter.com links.

Media links embed in discord but longer and bigger videos require embed bypass [https://discord.nfp.is](https://discord.nfp.is)

Inserts captions into video if avaliable (using ffmpeg), if caption_videos is True, burns them in.

Capability to download manifest (DASH) formats.

New class Grok to start chats with and generate images with (requires authentication).
## Setup
Written in Python 3.10.9
```bash
git clone https://github.com/Hecker5556/twitterdownloader.git
```
```bash
cd twitterdownloader
```
```bash
pip install -r requirements.txt
```

## Usage
```
usage: twitterdownloader.py [-h] [-m MAX_SIZE] [-r] link

positional arguments:
  link                  link to twitter post

options:
  -h, --help            show this help message and exit
  -m MAX_SIZE, --max-size MAX_SIZE
                        max size in mb of a video
  -r, --return-url      print urls of medias instead of download
```

```python
from twitterdownloader import TwitterDownloader
import asyncio
#non async
def main_():
    downloader = TwitterDownloader()
    result = asyncio.run(downloader.download("https://x.com/BronzeAya/status/1869967014695141528"))
    print(result)
#async
async def main():
    downloader = TwitterDownloader()
    result = await downloader.download("https://x.com/BronzeAya/status/1869967014695141528")
    print(result)
asyncio.run(main())
```
Grok
```python
from twitterdownloader import Grok
import asyncio
async def main():
  async with Grok() as grok:
    await grok.start_chat()
    result = await grok.add_response("hi how are you")
    print(result.get("message"))
    if result.get("images"):
      print(f"Following images have been generated:{a}{a.join([x.get('fileName') for x in result.get('images')])}")
asyncio.run(main())
```
## Get private/nsfw videos with authenticated fetching / use grok
### Step 1. Create an env.py file in the same directory as the code, and put this there
```python
guest_id = '' 
auth_token = '' 
csrf = ''
```
### Step 2. Go to twitter, find a nsfw/private video
Example: [https://x.com/sacredgraves/status/1707962195357630713?s=46](https://x.com/sacredgraves/status/1707962195357630713?s=46)
### Step 3. Open developer tab, go to network, hit refresh
### Step 4. search up tweetdetail

![hi](image.png)

### Step 5. Find the guest_id, auth_token and ct0

![hello2](image-1.png)

### Step 6. Add them to the env.py file, ct0 is the csrf token