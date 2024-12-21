import aiohttp, json, asyncio, re, os
from datetime import datetime, timedelta
from aiohttp_socks import ProxyConnector
from html import unescape
from typing import Literal
import mimetypes
from tqdm import tqdm
import traceback
LINKPATTERNS = [r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/?$', r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/(?:.*?)/\d$']
if not os.path.exists('features.json'):
    with open('features.json', 'w') as f1:
        f1.write("""{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":false,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":true,"rweb_tipjar_consumption_enabled":true, "creator_subscriptions_quote_tweet_preview_enabled":true, "rweb_tipjar_consumption_enabled": true, "creator_subscriptions_quote_tweet_preview_enabled": true}""")
with open("features.json", "r") as f1:
    FEATURES = json.load(f1)
class TwitterDownloader():
    def _give_connector(self, proxy: str):
        return aiohttp.TCPConnector() if not proxy or proxy.startswith("http") else ProxyConnector.from_url(proxy)
    def __init__(self, proxy: str = None, debug: bool = False):
        self.proxy = proxy
        self.debug = debug
        self.base_url = "https://video.twimg.com"
    async def download(self, link: str, max_size: int = None, return_media_url: bool = False, video_format: Literal['direct', 'dash'] = 'direct', caption_videos: bool = False):
        self.tweet_id = None
        for ptn in LINKPATTERNS:
            if id := re.search(ptn, link.split("?")[0]):
                self.tweet_id = id.group(1)
                self.link = id.group(0)
                break
        if not self.tweet_id:
            raise ValueError(f"Couldn't find links!")
        if not hasattr(self, "headers"):
            self.headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.7',
                'content-type': 'application/json',
                'origin': 'https://x.com',
                'priority': 'u=1, i',
                'referer': 'https://x.com/',
                'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Brave";v="128"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
                'x-twitter-active-user': 'yes',
                'x-twitter-client-language': 'en',
            }
        params = {
            'variables': json.dumps({"tweetId":self.tweet_id,"withCommunity":False,"includePromotedContent":False,"withVoice":False}),
            'features': json.dumps(FEATURES),
            'fieldToggles': '{"withArticleRichContentState":true,"withArticlePlainText":false,"withGrokAnalyze":false,"withDisallowedReplyControls":false}',        
        }
        async with aiohttp.ClientSession(connector=self._give_connector(self.proxy)) as session:
            if not hasattr(self, "session") or self.session.closed:
                self.session = session
            await self._get_bearer_token()
            if (not hasattr(self, "restid") or not isinstance(self.restid, str)) or (not hasattr(self, "tweetdetail") or not isinstance(self.tweetdetail, str)):
                if not os.path.exists("apiurls.json"):
                    self.restid, self.tweetdetail = await self._get_api_url()
                else:
                    with open("apiurls.json", "r") as f1:
                        thejson = json.load(f1)
                        self.restid, self.tweetdetail = thejson["restid"], thejson["tweetdetail"]
            self.headers['authorization'] = self.bearer
            guestoken = await self._get_guest_token()
            if not hasattr(self, "cookies"):
                self.cookies = {
                    'gt': guestoken
                }
            else:
                self.cookies["gt"] = guestoken
            self.headers['x-guest-token'] = guestoken
            proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
            async with self.session.get(self.restid, cookies=self.cookies,params=params, headers=self.headers, proxy=proxy) as r:
                a = await r.json()
                if self.debug:
                    with open("response.json", "w") as f1:
                        json.dump(a, f1)
            if not a.get('data'):
                new_features = a['errors'][0]['message'].split(': ')[1].split(', ')
                for ft in new_features:
                    if self.debug:
                        print(f"adding new feature {ft} to features")
                    FEATURES[ft] = True
                with open('features.json', 'w') as f1:
                    json.dump(FEATURES, f1)
                params = {
                    'variables': json.dumps({"tweetId":self.tweet_id,"withCommunity":False,"includePromotedContent":False,"withVoice":False}),
                    'features': json.dumps(FEATURES)
                }
                async with self.session.get(self.restid, cookies=self.cookies, headers=self.headers, params=params, proxy=proxy) as r:
                    a = await r.json()
                    if self.debug:
                        with open("response.json", "w") as f1:
                            json.dump(a, f1) 
            if not a['data']['tweetResult'].get("result") or (a["data"]["tweetResult"]["result"].get("__typename") and a["data"]["tweetResult"]["result"].get("__typename") == "TweetUnavailable"):
                if not os.path.exists("env.py"):
                    raise Exception("no credentials detected, make an env.py file, put csrf token, guest_id, auth_token there")
                from env import csrf, auth_token, guest_id
                self.csrf = csrf
                self.auth_token = auth_token
                self.guest_id = guest_id
                result = await self._get_authenticated_tweet()
            else:
                result = await self._tweet_result_parser(a['data']['tweetResult']["result"])
            if not result.get("medias"):
                return result
            result['medias'] = await self._parse_media(result['medias'])
            self.result = result
            if return_media_url:
                return result
            self.filenames = []
            for idx, media in enumerate(result['medias']):
                if media['type'] == 'video' or media['type'] == 'animated_gif':
                    videos = media['variants'][video_format]
                    if not videos:
                        raise Exception(f"Couldn't get media with that video format, check if nsfw?")
                    self.subtitles = media['variants']['dash'][0]['subtitle'] if not self.result.get('nsfw') and media['variants'].get('dash') else None
                    downloaded = False
                    for video in videos:
                        if (max_size and video['size'] <= max_size*1024*1024) or (not max_size):
                            filename = f"{self.result.get('author')['username']}-{int(datetime.now().timestamp())}-{idx}"
                            filename = await self._downloader(video if video_format == 'dash' else video['url'], filename, 'video_dash' if video_format == 'dash' else 'video_direct', caption=caption_videos)
                            self.filenames.append(filename)
                            downloaded = True
                            break
                    if not downloaded:
                        print(f"Couldn't download {idx}{'st' if idx == 0 else 'nd' if idx == 1 else 'rd' if idx == 2 else 'th'} file, every format is too large")
                else:
                    filename = f"{self.result.get('author')['username']}-{int(datetime.now().timestamp())}-{idx}"
                    filename = await self._downloader(media['url'], filename, type="photo")
                    self.filenames.append(filename)
            self.result['filenames'] = self.filenames
            return self.result
    async def _fetch_subs(self, url):
        async with self.session.get(url) as r:
            rtext = await r.text()
            match = re.search(r"#EXTINF:\d+\.\d+,\n(.*?)\.(.*?)\n", rtext)
            ext = match.group(2)
            subtitle = match.group(1)
        sub = f"{self.result.get('author')['username']}-{int(datetime.now().timestamp())}.{ext}"
        with open(sub, 'wb') as f1:
            async with self.session.get(self.base_url + subtitle + '.' + ext) as r:
                while True:
                    chunk = await r.content.read(1024)
                    if not chunk:
                        break
                    f1.write(chunk)
        return sub
    async def _downloader(self, url: str|dict, filename: str, type: Literal['video_dash', 'video_direct', 'photo'], caption: bool = False):
        if type == "video_direct" or type == "photo":
            async with self.session.get(url) as r:
                progress = tqdm(total=int(r.headers.get('content-length', '0')), unit='iB', unit_scale=True)
                ext = mimetypes.guess_extension(r.headers.get('content-type'))
                with open(filename + ext, 'wb') as f1:
                    while True:
                        chunk = await r.content.read(1024)
                        if not chunk:
                            break
                        f1.write(chunk)
                        progress.update(len(chunk))
                progress.close()
            if type == 'video_direct' and self.subtitles:
                temp = os.path.splitext(filename+ext)[0] + "temp" + ext
                os.rename(filename + ext, temp)
                sub = await self._fetch_subs(self.subtitles)
                command = ['-i', temp, ]
                if caption:
                    command += [ "-vf", f"subtitles={sub}"]
                else:
                    command += ['-i', sub,'-c', 'copy', "-c:s", "mov_text"]
                command += ["-y", filename + ext]
                process = await asyncio.create_subprocess_exec("ffmpeg", *command)
                await process.wait()
                os.remove(sub)
                os.remove(temp)
            return filename + ext
        elif type == 'video_dash':
            temp_files = []
            subtitle = url.get('subtitle')
            audio = url.get('audio')
            link = url.get('url')
            vid_ext = 'mp4' if 'avc1' in url.get('codecs') else 'mov'
            vid = f"{self.result.get('author')['username']}-{int(datetime.now().timestamp())}-temp.{vid_ext}"
            await self._manifest_downloader(link, vid, vid_ext)
            temp_files.append(vid)
            ext = 'm4a' if 'mp4a' in url.get('codecs') else 'mp3'
            aud = f"{self.result.get('author')['username']}-{int(datetime.now().timestamp())}.{ext}"
            await self._manifest_downloader(audio, aud, ext)
            temp_files.append(aud)
            sub = await self._fetch_subs(subtitle)
            temp_files.append(sub)
            command = ["-i", vid, "-i", aud, ]
            if caption:
                command += ["-vf", f"subtitles={sub}"]
            else:
                command += ["-i", sub, "-c", "copy", "-c:s", "mov_text"]
            command += ["-y", filename + '.' + vid_ext]
            process = await asyncio.create_subprocess_exec("ffmpeg", *command)
            await process.wait()
            [os.remove(file) for file in temp_files]
            return filename + '.' + vid_ext

    async def _manifest_downloader(self, url: str, filename: str, ext: str):
        async with self.session.get(url) as r:
            rtext = await r.text()
        start_pattern = r"MAP:URI=\"(.*?)\.(.*?)\""
        rest_pattern = r"#EXTINF:\d+\.\d+,\n(.*?)\n"
        matches = re.search(start_pattern, rtext)
        link = matches.group(1)
        ext = matches.group(2) if matches.group(2) != ext else ext
        link = self.base_url + link + "." + ext
        with open(filename, 'wb') as f1:
            async with self.session.get(link) as r:
                while True:
                    chunk = await r.content.read(1024)
                    if not chunk:
                        break
                    f1.write(chunk)
            urls = re.findall(rest_pattern, rtext)
            for i in urls:
                async with self.session.get(self.base_url + i) as r:
                    while True:
                        chunk = await r.content.read(1024)
                        if not chunk:
                            break
                        f1.write(chunk)

    async def _parse_media(self, media: dict):
        medias = []
        proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
        subtitles_pattern = r"\#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID=\"(.*?)\",NAME=\"(.*?)\",(?:.*?)URI=\"(.*?)\""
        audios_pattern = r"#EXT-X-MEDIA:NAME=\"Audio\",TYPE=AUDIO,GROUP-ID=\"(.*?)\",AUTOSELECT=YES,URI=\"(.*?)\""
        videos_pattern = r"#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=(?:\d+?),BANDWIDTH=(\d+),RESOLUTION=(\d+)x(\d+),CODECS=\"(.*?)\",SUBTITLES=\"(.*?)\",AUDIO=\"(.*?)\"\n(.*?)\n"
        for i in media:
            mdia = {}
            if i['type'] == 'video' or i['type'] == 'animated_gif':
                mdia['type'] = i['type']
                mdia['thumbnail'] = i['media_url_https']
                mdia['variants'] = {"direct": [], "dash": []}
                duration = i['video_info']['duration_millis']/1000
                for j in i['video_info']['variants']:
                    if j['content_type'] == 'application/x-mpegURL':
                        async with self.session.get(j["url"], proxy=proxy) as r:
                            rtext = await r.text()
                        subtitles_match = re.findall(subtitles_pattern, rtext)
                        subtitles = []
                        for group_id, name, url in subtitles_match:
                            subtitles.append({"id": group_id, "name": name, "url": self.base_url + url})
                        audios_match = re.findall(audios_pattern, rtext)
                        audios = []
                        for group_id, url in audios_match:
                            audios.append({"id": group_id, "url": self.base_url + url})
                        videos_match = re.findall(videos_pattern, rtext)
                        videos = []
                        for bitrate, width, height, codecs, subtitle, audio, url in videos_match:
                            for sb in subtitles:
                                if sb['id'] == subtitle:
                                    subtitle = sb['url']
                                    break
                            for ad in audios:
                                if ad['id'] == audio:
                                    audio = ad['url']
                                    break
                            videos.append({"bitrate": int(bitrate), "height": height, "width": width, "codecs": codecs, "subtitle": subtitle, "audio": audio, "url": self.base_url + url, "size": ((int(bitrate)*duration)/8)*0.9, "size_mb": (((int(bitrate)*duration)/8)*0.9)/(1024*1024), "type": "dash"})
                        mdia['variants']["dash"] += videos
                    else:
                        match = re.search(r"https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(?:.*?)vid/(?:.*?)/(\d+)x(\d+)/", j['url'])
                        mdia['variants']["direct"].append({"bitrate": int(j['bitrate']), "url": j['url'], "height": match.group(2), "width": match.group(1), "size": (((int(j['bitrate']))*duration)/8)*0.9, "size_mb": (((int(j['bitrate']))*duration)/8)*0.9/(1024*1024), "type": "direct"})
                mdia['variants'] = {"direct": list(sorted(mdia['variants']['direct'], key=lambda x: x.get('size'), reverse=True)), "dash": list(sorted(mdia['variants']['dash'], key=lambda x: x.get('size'), reverse=True))}
            elif i['type'] == 'photo':
                mdia['type'] = i['type']
                mdia['url'] = i['media_url_https']
                mdia['height'] = i['original_info']['height']
                mdia['width'] = i['original_info']['width']
            medias.append(mdia)
        return medias
    async def _get_authenticated_tweet(self):
        proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
        cookies = {
            'guest_id': self.guest_id,
            'auth_token': self.auth_token,
            'ct0': self.csrf,
        }
        headers = {
            'authority': 'twitter.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.7',
            'authorization': self.bearer,
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-csrf-token': self.csrf,
        }
        params = {
            'variables': json.dumps({"focalTweetId":self.tweet_id,"with_rux_injections":False,"includePromotedContent":True,"withCommunity":True,"withQuickPromoteEligibilityTweetFields":True,"withBirdwatchNotes":True,"withVoice":True,"withV2Timeline":True}),
            'features': json.dumps(FEATURES),
            'fieldToggles': '{"withArticleRichContentState":true,"withArticlePlainText":false,"withGrokAnalyze":false,"withDisallowedReplyControls":false}',
        }
        async with self.session.get(self.tweetdetail, cookies=cookies, headers=headers, params=params, proxy=proxy) as r:
            result = await r.json()
            if self.debug:
                with open("response.json", "w") as f1:
                    json.dump(result, f1, indent=4)
        for i in result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][::-1]:
            if "tweet" in i.get("entryId"):
                entry = i
                break
        resp_type = False if entry["content"].get("items") else True
        if not resp_type:
            tweet_results = entry["content"]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
        else:
            tweet_results = entry["content"]["itemContent"]["tweet_results"]["result"]
        if typename := tweet_results.get("__typename"):
            if "Tombstone" in typename:
                raise Exception(f"Errored! {tweet_results['tombstone']['text']['text']}")
        if not tweet_results.get("legacy"):
            tweet_results = tweet_results["tweet"]
        return await self._tweet_result_parser(tweet_results)
    async def _tweet_result_parser(self, tweet_results: dict) -> dict:
        info = {}
        info['medias'] = tweet_results["legacy"]["entities"].get("media")


        info['author'] = {"username": "".join([x for x in tweet_results["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()']),
                        "nick": tweet_results["core"]["user_results"]["result"]["legacy"]["name"],
                        "link": f'https://x.com/{tweet_results["core"]["user_results"]["result"]["legacy"]["screen_name"]}',
                        "avatar": tweet_results['core']['user_results']['result']['legacy'].get('profile_image_url_https')}
        if note_tweet := tweet_results.get("note_tweet"):
            info["full_text"] = unescape(note_tweet['note_tweet_results']['result'].get("text"))
        else:
            info["full_text"] = unescape(tweet_results["legacy"]["full_text"])
        if quoted := tweet_results.get("quoted_status_result"):
            info["quoted"] = {}
            if quoted_media := quoted["result"]["legacy"]["entities"].get("media"):
                info["quoted"]["media"] = [x.get('media_url_https') if not x.get('video_info') else x['video_info']['variants'][-1]['url'] for x in quoted_media]
            info["quoted"]["full_text"] = unescape(quoted["result"]["legacy"].get('full_text'))
            info["quoted"]['author'] = {"username": "".join([x for x in quoted["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()']), 
                                        "nick": quoted["result"]["core"]["user_results"]["result"]["legacy"]["name"],
                                        "link": f'https://x.com/{quoted["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"]}',
                                        "avatar": quoted["result"]['core']['user_results']['result']['legacy'].get('profile_image_url_https')}
            info["quoted"]['link'] = tweet_results['legacy'].get('quoted_status_permalink').get('expanded')
        elif reply := tweet_results['legacy'].get("in_reply_to_status_id_str"):
            info["replying_to"] = await self.download(f'https://x.com/{tweet_results["legacy"].get("in_reply_to_screen_name")}/status/{reply}', return_media_url=True)
        info["link"] = f"https://x.com/{info['author']['username']}/status/{tweet_results['legacy']['id_str']}"
        info["date_posted"] = datetime.strptime(tweet_results['legacy'].get('created_at'), "%a %b %d %H:%M:%S %z %Y").timestamp()
        info["bookmarks"] = tweet_results['legacy'].get("bookmark_count")
        info["likes"] = tweet_results['legacy'].get("favorite_count")
        info["quotes"] = tweet_results['legacy'].get("quote_count")
        info["replies"] = tweet_results['legacy'].get("reply_count")
        info["retweets"] = tweet_results['legacy'].get("retweet_count")
        info["views"] = tweet_results['views']['count']
        if tweet_results['legacy'].get("possibly_sensitive"):
            info["nsfw"] = True
        return info
    async def _get_guest_token(self):
        async with self.session.post('https://api.twitter.com/1.1/guest/activate.json', headers=self.headers, proxy=self.proxy) as r:
            a = await r.json()
            return a['guest_token']
    async def _get_api_url(self):
        proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
        if not hasattr(self, "jslink"):
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            async with self.session.get(self.link, headers=self.headers, proxy=proxy) as r:
                text = await r.text('utf-8')
                matches = re.search(pattern ,text)
            if not matches:
                await self._post_data()
                async with self.session.get(self.link, headers=self.headers, proxy=proxy) as r:
                    text = await r.text('utf-8')
                    matches = re.search(pattern ,text)
            self.jslink = matches.group()
        pattern2 = r'{queryId:\"(.*?)\",operationName:\"TweetResultByRestId\"'
        pattern3 = r'queryId:\"(.*?)\",operationName:\"TweetDetail\"'
        async with self.session.get(self.jslink, headers=self.headers, proxy=proxy) as r:
            js = await r.text()
        location1 = js[js.find("TweetResultByRestId")-50:js.find("TweetResultByRestId")+50]
        location2 = js[js.find("TweetDetail")-50:js.find("TweetDetail")+50]
        restid = re.search(pattern2, location1).group()
        tweetdetail = re.search(pattern3, location2).group()
        restid = f'https://api.twitter.com/graphql/{restid}/TweetResultByRestId'
        tweetdetail = f'https://twitter.com/i/api/graphql/{tweetdetail}/TweetDetail'
        thejson = {"restid": restid, "tweetdetail": tweetdetail}
        with open("apiurls.json", "w") as f1:
            json.dump(thejson, f1)
        return restid, tweetdetail
    async def _get_bearer_token(self):
        if not hasattr(self, "bearer") or not isinstance(self.bearer, str):
            if os.path.exists("bearer_token.txt"):
                with open("bearer_token.txt", "r") as f1:
                    self.bearer = f1.read()
                return self.bearer
            else:
                await self._post_data()
                proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
                async with self.session.get(self.link, headers=self.headers, proxy=proxy, params={"mx": 2}) as r:
                    pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
                    text = await r.text()
                    matches = re.search(pattern, text)
                    if not matches:
                        raise Exception("couldnt get bearer token javascript")
                self.jslink = matches.group(0)
                async with self.session.get(self.jslink, proxy=proxy) as r:
                    pattern = r'\"(Bearer (?:.*?))\"'
                    while True:
                        chunk = await r.content.read(1024*10)
                        if not chunk:
                            break
                        matches = re.findall(pattern, chunk.decode("utf-8"))
                        if matches:
                            break
                if not matches:
                    raise Exception(f"Couldn't find bearer token.")
                with open("bearer_token.txt", "w") as f1:
                    f1.write(matches[-1])
                return matches
    async def _post_data(self):
        proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None
        async with self.session.get(self.link, headers=self.headers, proxy=proxy) as r:
            pattern_redirect = r"document\.location = \"(.*?)\"</script>"
            text = await r.text()
            matches = re.search(pattern_redirect, text).group(1)
            async with self.session.get(matches, headers=self.headers, proxy=proxy) as r:
                tok = r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />"
                text = await r.text()
                tok = re.search(r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />", text).group(1)
                data = re.search(r"<input type=\"hidden\" name=\"data\" value=\"(.*?)\" />", text).group(1)
                refresh = re.search(r"<meta http-equiv=\"refresh\" content=\"\d+; url = (.*?)\" />", text).group(1)
                payload = {"data": data, "tok": tok}
                url = re.search(r"<form action=\"(.*?)\"", text).group(1)
                async with self.session.post(url, data=json.dumps(payload), headers=self.headers, proxy=proxy) as r:
                    pass
                async with self.session.get(refresh, headers=self.headers, proxy=proxy) as r:
                    pass
class Grok(TwitterDownloader):
    async def __aenter__(self):
        self.data = {"responses":
                    [
                    ],
                    "systemPromptName":"",
                    "grokModelOptionId":"grok-2a",
                    "conversationId":None,
                    "returnSearchResults":True,
                    "returnCitations":True,
                    "promptMetadata":
                        {
                            "promptSource":"NATURAL",
                            "action":"INPUT"
                        },
                    "imageGenerationCount":4,
                    "requestFeatures":
                        {
                            "eagerTweets":True,
                            "serverHistory":True
                        }
                }
        self.started = False
        return self
    async def __aexit__(self, a, b, c):
        if a:
            print(traceback.format_exception(a, b, c))
        await self.session.close()
    async def start_chat(self, ):
        if os.path.exists("queryIdcache.txt"):
            with open("queryIdcache.txt", "r") as f1:
                aaa = f1.read().split("\t")
                if datetime.fromisoformat(aaa[1]) > datetime.now():
                    self.queryId = aaa[0]
                else:
                    self.queryId = None
        else:
            self.queryId = None
        if not hasattr(self, "session") or self.session.closed:
            self.session = aiohttp.ClientSession(connector=self._give_connector(self.proxy))
        await self._get_bearer_token()
        from env import guest_id, auth_token, csrf
        self.cookies = {
        'dnt': '1',
        'guest_id': guest_id,
        'night_mode': '2',
        'auth_token': auth_token,
        'ct0': csrf,
        'lang': 'en',
        }
        if not self.queryId:
            headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.6',
            'cache-control': 'max-age=0',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }
            proxy = self.proxy if self.proxy and self.proxy.startswith("http") else None

            async with self.session.get("https://x.com/i/grok", proxy=proxy, headers=headers, cookies=self.cookies) as r:
                rtext = await r.text("utf-8")
            js_pattern = r"\"(shared~bundle\.Grok~bundle\.ReaderMode~bundle\.Birdwatch~bundle\.TwitterArticles~bundle\.Compose~bundle\.Settings~b)\":\"(.*?)\""
            js_match = re.search(js_pattern, rtext)
            part_1 = js_match.group(1)
            part_2 = js_match.group(2)
            base_url = "https://abs.twimg.com/responsive-web/client-web/"
            async with self.session.get(base_url + part_1 + '.' + part_2 + "a" + ".js", proxy=proxy) as r:
                js_text = await r.text("utf-8")
            queryId_pattern = r":\"(.*?)\",operationName:\"CreateGrokConversation\",.*?}}"
            js_text = js_text.split("queryId")
            for i in js_text:
                if queryId:=re.search(queryId_pattern, i):
                    queryId = queryId.group(1)
                    break
            self.queryId = queryId
            with open("queryIdcache.txt", "w") as f1:
                expiry = (datetime.now() + timedelta(days=7)).isoformat()
                f1.write(f"{self.queryId}\t{expiry}")
        self.base_url_grok = "https://x.com/i/api/graphql/"+self.queryId+"/"
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.8',
            'authorization': self.bearer,
            'content-type': 'application/json',
            'origin': 'https://x.com',
            'priority': 'u=1, i',
            'referer': 'https://x.com/i/grok',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-csrf-token': csrf,
        }
        data = {
            "queryId": self.queryId,
            "variables": {}
        }
        async with self.session.post(self.base_url_grok + "CreateGrokConversation", headers=self.headers, cookies=self.cookies, data=json.dumps(data)) as r:
            response = await r.json()
            self.conversation_id = response["data"]["create_grok_conversation"]["conversation_id"]
            self.data["conversationId"] = self.conversation_id
        self.started = True
    async def add_response(self, message: str, file: str = None):
        if not self.started:
            raise Exception(f"Run start_chat() before adding a response. If manually using your own values, set the Grok object 'started' attribute to True")
        headers = {
            'sec-ch-ua-platform': '"Windows"',
            'authorization': self.bearer,
            'x-csrf-token': self.headers.get("x-csrf-token"),
            'Referer': 'https://x.com/',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'x-twitter-client-language': 'en',
            'sec-ch-ua-mobile': '?0',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        self.data["responses"].append({
                            "message":message,
                            "sender":1,
                            "promptSource":"",
                            "fileAttachments":[]
                        })
        if file:
            if not os.path.exists(file):
                if not file.startswith("http"):
                    raise FileNotFoundError(f"Couldn't find {file}")
                else:
                    async with self.session.get(file) as r:
                        if "image" not in r.headers.get("content-type") or "pdf" not in r.headers.get("content-type"):
                            raise ValueError(f"File must be an image")
                        ext = mimetypes.guess_extension(r.headers.get("content-type"))
                        file = f"grok_file-{int(datetime.now().timestamp())}{ext}"
                        with open(file, "wb") as f1:
                            while True:
                                chunk = await r.content.read(1024)
                                if not chunk:
                                    break
                                f1.write(chunk)
            if "image" not in mimetypes.guess_type(file)[0] or "pdf" not in mimetypes.guess_type(file)[0]:
                raise ValueError(f"File must be an image")
            data = aiohttp.FormData()
            data.add_field("image", open(file, 'rb'), content_type=mimetypes.guess_type(file)[0])
            _headers = {
                'sec-ch-ua-platform': '"Windows"',
                'x-csrf-token': self.headers.get("x-csrf-token"),
                'authorization': self.bearer,
                'Referer': 'https://x.com/i/grok',

                'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'x-twitter-client-language': 'en',
                'sec-ch-ua-mobile': '?0',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }
            async with self.session.post("https://x.com/i/api/2/grok/attachment.json", headers=_headers, cookies=self.cookies, data=data) as r:
                response = await r.json()
                self.data["responses"][-1]["fileAttachments"] += response
        finished = {}
        async with self.session.post('https://api.x.com/2/grok/add_response.json', headers=headers, data=json.dumps(self.data), cookies=self.cookies) as r:
            result = ""
            json_results = []
            temp = bytearray()
            while True:
                chunk = await r.content.read(1)
                if not chunk:
                    break
                temp += chunk
                try:
                    a = json.loads(temp)
                    json_results.append(a)
                    temp = bytearray()
                except:
                    continue
            images = []
            for i in json_results:
                if i.get("result") and i['result'].get("message"):
                    result += i['result']['message']
                elif i.get('result') and i['result'].get("imageAttachment"):
                    images.append(i['result']['imageAttachment'])
            for img in images:
                async with self.session.get(img['imageUrl'], cookies=self.cookies, headers=headers) as r:
                    with open(img['fileName'], 'wb') as f1:
                        while True:
                            chunk = await r.content.read(1024)
                            if not chunk:
                                break
                            f1.write(chunk)
            finished["images"] = images
            self.data["responses"].append({
                            "message":result,
                            "sender":2,
                        })
            finished["message"] = result
            return finished
async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("link", help="link to twitter post")
    parser.add_argument("-m", "--max-size", type=float, help="max size in mb of a video")
    parser.add_argument("-r", "--return-url", action="store_true", help="returns urls of medias instead of download")
    parser.add_argument("-p", "--proxy", type=str, help="https/socks proxy to use")
    parser.add_argument("-d", "--dash",default=False, action="store_true", help="download dash video format instead of direct")
    parser.add_argument("-c", "--caption", action="store_true", help="burn in twitter given captions into the video")
    args = parser.parse_args()
    result = await TwitterDownloader(args.proxy).download(args.link, args.max_size, args.return_url, "dash" if args.dash else "direct", args.caption)
    print(result)
async def chatting():
    a = '\n'
    async with Grok() as grok:
        await grok.start_chat()
        while True:
            you = str(input("QUERY: "))
            response = await grok.add_response(you)
            print("GROK: " + response['message'])
            if response.get('images'):
                print(f"Following images have been generated:{a}{a.join([x.get('fileName') for x in response.get('images')])}")
if __name__ == "__main__":
    asyncio.run(chatting())