import aiohttp, aiofiles, asyncio, re, datetime, os, json
from tqdm.asyncio import tqdm
from datetime import datetime
from aiohttp_socks import ProxyConnector
FEATURES = {"responsive_web_graphql_exclude_directive_enabled":True,"verified_phone_label_enabled":False,"creator_subscriptions_tweet_preview_api_enabled":True,"responsive_web_graphql_timeline_navigation_enabled":True,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":False,"c9s_tweet_anatomy_moderator_badge_enabled":True,"tweetypie_unmention_optimization_enabled":True,"responsive_web_edit_tweet_api_enabled":True,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,"view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,"responsive_web_twitter_article_tweet_consumption_enabled":False,"tweet_awards_web_tipping_enabled":False,"freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,"rweb_video_timestamps_enabled":False,"longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":True,"responsive_web_media_download_video_enabled":False,"responsive_web_enhance_cards_enabled":False,"communities_web_enable_tweet_community_results_fetch":True,"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":True,"rweb_tipjar_consumption_enabled":True, "creator_subscriptions_quote_tweet_preview_enabled":True, "rweb_tipjar_consumption_enabled, creator_subscriptions_quote_tweet_preview_enabled": True}
class twitterdownloader:
    class invalidlink(Exception):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)
    class missingcredentials(Exception):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)
    class videotoobig(Exception):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)
    async def get_guest_token(session: aiohttp.ClientSession, headers: dict, proxy: str = None) -> str:
        async with session.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            a = await r.json()
            return a['guest_token']
    def createconnector(proxy: str):
        return aiohttp.TCPConnector() if (not proxy or proxy and proxy.startswith("sock")) else ProxyConnector.from_url(proxy)
    async def get_api_url(session: aiohttp.ClientSession, link: str, headers: dict, proxy: str = None) -> tuple[str, str]:
        pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
        async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            while True:
                chunk = await r.content.read(1024*2)
                if not chunk:
                    break
                decoded = chunk.decode("utf-8")
                matches = re.findall(pattern, decoded)
                if matches:
                    break
        jslink = matches[0]
        pattern2 = r'{queryId:\"(.*?)\",operationName:\"TweetResultByRestId\"'
        pattern3 = r'queryId:\"(.*?)\",operationName:\"TweetDetail\"'
        async with session.get(jslink) as r:
            js = await r.text()
        location1 = js[js.find("TweetResultByRestId")-50:js.find("TweetResultByRestId")+50]
        location2 = js[js.find("TweetDetail")-50:js.find("TweetDetail")+50]
        restid = re.findall(pattern2, location1)[0]
        tweetdetail = re.findall(pattern3, location2)[0]
        restid = f'https://api.twitter.com/graphql/{restid}/TweetResultByRestId'
        tweetdetail = f'https://twitter.com/i/api/graphql/{tweetdetail}/TweetDetail'
        thejson = {"restid": restid, "tweetdetail": tweetdetail}
        async with aiofiles.open("apiurls.json", "w") as f1:
            await f1.write(json.dumps(thejson))
        return restid, tweetdetail
    async def get_bearer_token(session: aiohttp.ClientSession, link: str, headers: dict, proxy: str = None) -> str:
        async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            text = await r.text()
            matches = re.findall(pattern, text)
            if not matches:
                raise twitterdownloader.invalidlink("invalid link idk")
        jslink = matches[0]
        async with session.get(jslink, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            pattern = r'\"(Bearer (?:.*?))\"'
            while True:
                chunk = await r.content.read(1024*10)
                if not chunk:
                    break
                matches = re.findall(pattern, chunk.decode("utf-8"))
                if matches:
                    break
        if not matches:
            raise twitterdownloader.invalidlink("invalid link idk")
        async with aiofiles.open("bearer_token.txt", "w") as f1:
            await f1.write(matches[0])
        return matches[0]
    async def get_authenticated_tweet(tweet_id: int, csrf: str, guest_id: str, auth_token: str, bearer_token: str, session: aiohttp.ClientSession, apiurl: str, proxy: str = None):
        cookies = {
            'guest_id': guest_id,
            'auth_token': auth_token,
            'ct0': csrf,
        }
        headers = {
            'authority': 'twitter.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.7',
            'authorization': bearer_token,
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-csrf-token': csrf,
        }
        params = {
            'variables': '{"focalTweetId":%s,"with_rux_injections":false,"includePromotedContent":true,"withCommunity":true,"withQuickPromoteEligibilityTweetFields":true,"withBirdwatchNotes":true,"withVoice":true,"withV2Timeline":true}' % tweet_id,
            'features': json.loads(FEATURES),
            'fieldToggles': '{"withArticleRichContentState":false}',
        }
        async with session.get(apiurl, cookies=cookies, headers=headers, params=params, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            result = await r.json()

        medias = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"].get("tweet")
        if not medias:
            medias = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["entities"].get("media")
        author = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"].get("tweet")
        if not author:
            author = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"]
        author = "".join([x for x in author if x not in '\\/:*?"<>|()'])
        fulltext = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"].get("tweet")
        if not fulltext:
            fulltext = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][0]["content"]["itemContent"]["tweet_results"]["result"]["legacy"]["full_text"]
        return medias, author, fulltext
    async def downloader(link: str, filename: str, session: aiohttp.ClientSession, proxy: str = None):
        async with aiofiles.open(filename, 'wb') as f1:
            async with session.get(link, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                total = int(r.headers.get('content-length'))
                progress = tqdm(total=total, unit='iB', unit_scale=True)
                while True:
                    chunk = await r.content.read(1024)
                    if not chunk:
                        break
                    await f1.write(chunk)
                    progress.update(len(chunk))
                progress.close()
    async def download(link: str, maxsize: int = None, returnurl: bool = False, proxy: str = None):
        link = link.split('?')[0]
        pattern = r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/?$'
        pattern2 = r"https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/(?:.*?)/\d$"
        tweet_id = re.findall(pattern, link)
        if not tweet_id:
            tweet_id = re.findall(pattern2, link)
            if not tweet_id:
                raise twitterdownloader.invalidlink("the link is invalid i think")
        
        tweet_id = tweet_id[0]
        headers = {
            'authority': 'api.twitter.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.6',
            'content-type': 'application/json',
            'origin': 'https://twitter.com',
            'referer': 'https://twitter.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        params = {
            'variables': '{"tweetId":%s,"withCommunity":false,"includePromotedContent":false,"withVoice":false}' % tweet_id,
            'features': json.loads(FEATURES)
        }
        async with aiohttp.ClientSession(connector=twitterdownloader.createconnector(proxy)) as session:
            if not os.path.exists("bearer_token.txt"):
                bearer = await twitterdownloader.get_bearer_token(session, link, headers, proxy)
            else:
                async with aiofiles.open("bearer_token.txt", "r") as f1:
                    bearer = await f1.read()
            if not os.path.exists("apiurls.json"):
                restid, tweetdetail = await twitterdownloader.get_api_url(session, link, headers, proxy)
            else:
                async with aiofiles.open("apiurls.json", "r") as f1:
                    thejson = await f1.read()
                    thejson = json.loads(thejson)
                    restid, tweetdetail = thejson["restid"], thejson["tweetdetail"]
            headers['authorization'] = bearer
            guestoken = await twitterdownloader.get_guest_token(session, headers, proxy)
            cookies = {
                'gt': guestoken
            }
            headers['x-guest-token'] = guestoken
            async with session.get(restid, cookies=cookies, headers=headers, params=params, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                a = await r.json()
                async with aiofiles.open("response.json", "w") as f1:
                    await f1.write(json.dumps(a))
            if a["data"]["tweetResult"]["result"].get("__typename") and a["data"]["tweetResult"]["result"].get("__typename") == "TweetUnavailable":
                if not os.path.exists("env.py"):
                    raise twitterdownloader.missingcredentials("no credentials detected, make an env.py file, put csrf token, guest_id, auth_token there")
                from env import csrf, auth_token, guest_id
                result = await twitterdownloader.get_authenticated_tweet(tweet_id, csrf, guest_id, auth_token, bearer, session, tweetdetail, proxy)
                medias = result[0]
                fulltext = result[2]
                author = result[1]
            else:
                medias = a["data"]["tweetResult"]["result"]["legacy"]["entities"].get("media")
                fulltext = a["data"]["tweetResult"]["result"]["legacy"].get('full_text')
                author = "".join([x for x in a["data"]["tweetResult"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()'])
            if fulltext:
                fulltext = fulltext.encode('utf-16', 'surrogatepass').decode('utf-16')
            if not medias:
                print("no medias found")
                return {"caption": fulltext, "author": author}
            media_urls = []
            duration = 0
            for media in medias:
                if media.get("video_info"):
                    duration = media["video_info"]["duration_millis"]
                    videos = []
                    for variant in media["video_info"]["variants"]:
                        videos.append((variant["url"], variant.get('bitrate')))
                    media_urls.append(videos)
                    continue
                if media.get("media_url_https"):
                    media_urls.append(media.get("media_url_https"))
            if returnurl:
                return {"mediaurls": media_urls, "author": author, "caption": fulltext}
            filenames = []
            for mindex, media in enumerate(media_urls):
                if isinstance(media, list):
                    if maxsize:
                        sizes = {}
                        for index, video in enumerate(media):
                            if ".m3u8?tag=" in video[0]:
                                continue
                            sizes[index] = ((((video[1] * duration) / 1000)/8) / (1024*1024)) * 0.9
                        if len(media) == 1:
                            await twitterdownloader.downloader(media[0], filename, session, proxy)
                            continue
                        sizes = sorted(sizes.items(), key=lambda x: float(x[1]), reverse=True)
                        print(sizes)
                        downloaded = False
                        for index, size in sizes:
                            if size < maxsize:
                                filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                                filenames.append(filename)
                                print(media[index][0])
                                await twitterdownloader.downloader(media[index][0], filename, session, proxy)
                                downloaded = True
                                break
                        if not downloaded:
                            raise twitterdownloader.videotoobig("video too large to download")
                    else:
                        filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                        filenames.append(filename)
                        if len(media) == 1:
                            await twitterdownloader.downloader(media[0], filename, session, proxy)
                            continue
                        resolutions = {}
                        pattern = r'((?:\d*?)x(?:\d*?))/'
                        for index, video in enumerate(media):
                            matches = re.findall(pattern, video[0])
                            if not matches:
                                continue
                            uh = 1
                            the = [int(x) for x in matches[0].split("x")]
                            for i in the:
                                uh = uh * i
                            resolutions[index] = uh
                        resolutions = sorted(resolutions.items(), key=lambda x: x[1], reverse=True)
                        await twitterdownloader.downloader(media[resolutions[0][0]][0], filename, session, proxy)
                else:
                    filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.jpg'
                    filenames.append(filename)
                    await twitterdownloader.downloader(media, filename, session, proxy)
            return {"filenames": filenames, "author": author, "caption": fulltext}
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("link", help="link to twitter post")
    parser.add_argument("-m", "--max-size", type=int, help="max size in mb of a video")
    parser.add_argument("-r", "--return-url", action="store_true", help="print urls of medias instead of download")
    parser.add_argument("-p", "--proxy", type=str, help="https/socks proxy to use")
    args = parser.parse_args()
    print(asyncio.run(twitterdownloader.download(args.link, args.max_size, args.return_url, args.proxy)))