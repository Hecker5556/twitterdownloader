import aiohttp, json, asyncio, re, os
from datetime import datetime, timedelta
from aiohttp_socks import ProxyConnector
from html import unescape
from typing import Literal
import mimetypes
from tqdm import tqdm
import traceback
LINKPATTERNS = [r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/?$', r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/(?:.*?)/\d$']
MAX_FIELD_SIZE = 11000
if not os.path.exists('features.json'):
    with open('features.json', 'w') as f1:
        f1.write("""{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":false,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":true,"rweb_tipjar_consumption_enabled":true, "creator_subscriptions_quote_tweet_preview_enabled":true, "rweb_tipjar_consumption_enabled": true, "creator_subscriptions_quote_tweet_preview_enabled": true}""")
with open("features.json", "r") as f1:
    FEATURES = json.load(f1)
class TwitterDownloader():
    def _give_connector(self, proxy: str):
        return aiohttp.TCPConnector() if not proxy else ProxyConnector.from_url(proxy)
    def __init__(self, proxy: str = None, debug: bool = False):
        self.proxy = proxy
        self.debug = debug
        self.base_url = "https://video.twimg.com"
        self.subtitles = None
        self.no_ffmpeg = False
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
        async with aiohttp.ClientSession(connector=self._give_connector(self.proxy), max_field_size=MAX_FIELD_SIZE) as session:
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
            
            async with self.session.get(self.restid, cookies=self.cookies,params=params, headers=self.headers, ) as r:
                a = await r.json()
                if self.debug:
                    with open("response.json", "w") as f1:
                        json.dump(a, f1)
            if not a.get('data'):
                if a['errors'][0]['message'] == "Bad guest token":
                    os.remove("guesttoken.txt")
                    guestoken = await self._get_guest_token()
                    self.cookies["gt"] = guestoken
                    self.headers['x-guest-token'] = guestoken
                if self.debug:
                    print(a['errors'])
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
                async with self.session.get(self.restid, cookies=self.cookies, headers=self.headers, params=params, ) as r:
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
                        if (not video.get('size')) or (max_size and video['size'] <= max_size*1024*1024) or (not max_size) :
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
            if type == 'video_direct' and self.subtitles and not self.no_ffmpeg:
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
            if subtitle:
                sub = await self._fetch_subs(subtitle)
                temp_files.append(sub)
            command = ["-i", vid, "-i", aud,  "-c", "copy", ]
            if subtitle:
                if caption:
                    command += ["-vf", f"subtitles={sub}"]
                else:
                    command += ["-i", sub, "-c:s", "mov_text"]
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
        
        subtitles_pattern = r"\#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID=\"(.*?)\",NAME=\"(.*?)\",(?:.*?)URI=\"(.*?)\""
        audios_pattern = r"#EXT-X-MEDIA:NAME=\"Audio\",TYPE=AUDIO,GROUP-ID=\"(.*?)\",AUTOSELECT=YES,URI=\"(.*?)\""
        videos_pattern = r"#EXT-X-STREAM-INF:AVERAGE-BANDWIDTH=(?:\d+),BANDWIDTH=(\d+),RESOLUTION=(\d+)x(\d+),CODECS=\"(.*?)\",(?:SUBTITLES=\"(.*?)\",)?AUDIO=\"(.*?)\"\n(.*?)\n"
        for i in media:
            mdia = {}
            if i['type'] == 'video' or i['type'] == 'animated_gif':
                mdia['type'] = i['type']
                mdia['thumbnail'] = i['media_url_https']
                mdia['variants'] = {"direct": [], "dash": []}
                if i['type'] == 'video':
                    duration = i['video_info']['duration_millis']/1000
                    for j in i['video_info']['variants']:
                        if j['content_type'] == 'application/x-mpegURL':
                            async with self.session.get(j["url"], ) as r:
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
                            match = re.search(r"https://video\.twimg\.com/(?:ext_tw_video|amplify_video)/(?:.*?)vid/(?:.*?)/?(\d+)x(\d+)/", j['url'])
                            mdia['variants']["direct"].append({"bitrate": int(j['bitrate']), "url": j['url'], "height": match.group(2), "width": match.group(1), "size": (((int(j['bitrate']))*duration)/8)*0.9, "size_mb": (((int(j['bitrate']))*duration)/8)*0.9/(1024*1024), "type": "direct"})
                    mdia['variants'] = {"direct": list(sorted(mdia['variants']['direct'], key=lambda x: x.get('size'), reverse=True)), "dash": list(sorted(mdia['variants']['dash'], key=lambda x: x.get('size'), reverse=True))}
                else:
                    for j in i['video_info']['variants']:
                        mdia['variants']["direct"].append({"bitrate": int(j['bitrate']), "url": j['url'], "height": i['sizes']['large']['h'], "width": i['sizes']['large']['w'], "size": None, "size_mb": None, "type": "direct"})
            elif i['type'] == 'photo':
                mdia['type'] = i['type']
                mdia['url'] = i['media_url_https']
                mdia['height'] = i['original_info']['height']
                mdia['width'] = i['original_info']['width']
            medias.append(mdia)
        return medias
    async def _get_authenticated_tweet(self):
        
        cookies = {
            'guest_id': self.guest_id,
            'auth_token': self.auth_token,
            'ct0': self.csrf,
        }
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.7',
            'authorization': self.bearer,
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-csrf-token': self.csrf,
        }
        params = {
            'variables': json.dumps({"focalTweetId":self.tweet_id,"with_rux_injections":False,"rankingMode":"Relevance","includePromotedContent":True,"withCommunity":True,"withQuickPromoteEligibilityTweetFields":True,"withBirdwatchNotes":True,"withVoice":True}),
            'features': json.dumps(FEATURES),
            'fieldToggles': '{"withArticleRichContentState":true,"withArticlePlainText":false,"withGrokAnalyze":false,"withDisallowedReplyControls":false}',
        }
        async with self.session.get(self.tweetdetail, cookies=cookies, headers=headers, params=params, ) as r:
            result = await r.json()
            if self.debug:
                with open("response.json", "w") as f1:
                    json.dump(result, f1, indent=4)
        if not result.get('data'):
            if "following features cannot be null" in result['errors'][0]['message']:
                new_features = result['errors'][0]['message'].split(': ')[1].split(', ')
                for ft in new_features:
                    if self.debug:
                        print(f"adding new feature {ft} to features")
                    FEATURES[ft] = True
                with open('features.json', 'w') as f1:
                    json.dump(FEATURES, f1)
                params = {
                    'variables': json.dumps({"focalTweetId":self.tweet_id,"with_rux_injections":False,"rankingMode":"Relevance","includePromotedContent":True,"withCommunity":True,"withQuickPromoteEligibilityTweetFields":True,"withBirdwatchNotes":True,"withVoice":True}),
                    'features': json.dumps(FEATURES),
                    'fieldToggles': '{"withArticleRichContentState":true,"withArticlePlainText":false,"withGrokAnalyze":false,"withDisallowedReplyControls":false}',
                }
                async with self.session.get(self.tweetdetail, cookies=cookies, headers=headers, params=params, ) as r:
                    result = await r.json()
                    if self.debug:
                        with open("response.json", "w") as f1:
                            json.dump(result, f1, indent=4)
            else:
                raise Exception(f"Fetching data errored!: {result['errors'][0]['message']}")
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
    @staticmethod
    def _find_key(obj, searching_for: str, not_null: bool = True):
        path = []
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == searching_for:
                    if not_null and value:
                        path.append(key)
                        return path
                    elif not not_null:
                        path.append(key)
                        return path
                result = TwitterDownloader._find_key(value, searching_for, not_null)
                if result:
                    path.append(key)
                    path += result
                    return path
        elif isinstance(obj, list):
            for index, i in enumerate(obj):
                result = TwitterDownloader._find_key(i, searching_for, not_null)
                if result:
                    path.append(index)
                    path += result
                    return path
        return path
    @staticmethod
    def _path_parser(path):
        templist = []
        for i in path:
            if isinstance(i, str):
                templist.append(f"['{i}']")
            elif isinstance(i, int):
                templist.append(f"[{i}]")
        return ''.join(templist)
    async def _tweet_result_parser(self, tweet_results: dict) -> dict:
        info = {}
        attempt = self._find_key(tweet_results['legacy'], 'media')
        if attempt:
            info['medias'] = eval(f"tweet_results['legacy']{self._path_parser(attempt)}")
        else:
            info['medias'] = {}
        username = eval(f"tweet_results{self._path_parser(self._find_key(tweet_results, 'screen_name'))}")
        info['author'] = {"username": "".join([x for x in username if x not in '\\/:*?"<>|()']),
                        "nick": eval(f"tweet_results{self._path_parser(self._find_key(tweet_results, 'name'))}"),
                        "link": f'https://x.com/{username}',
                        "avatar": None}

        attempt = self._find_key(tweet_results, 'profile_image_url_https')
        if not attempt:
            info['author']['avatar'] = eval(f"tweet_results{self._path_parser(self._find_key(tweet_results, 'image_url'))}")
        else:
            info['author']['avatar'] = eval(f"tweet_results{self._path_parser(attempt)}")

        if note_tweet := tweet_results.get("note_tweet"):
            info["full_text"] = unescape(note_tweet['note_tweet_results']['result'].get("text"))
        else:
            info["full_text"] = unescape(tweet_results["legacy"]["full_text"])
        quoted = None
        if (quoted := tweet_results.get("quoted_status_result")) or tweet_results['legacy'].get("is_quote_status"):
            if not quoted:
                try:
                    info["quoted"] = await self.download(tweet_results['legacy'].get('quoted_status_permalink').get('expanded'), return_media_url=True)
                except:
                    info['quoted'] = {'link': tweet_results['legacy'].get('quoted_status_permalink').get('expanded')}
            else:

                info["quoted"] = {}
                username = eval(f"quoted{self._path_parser(self._find_key(quoted, 'screen_name'))}")
                if quoted_media := quoted["result"]["legacy"]["entities"].get("media"):
                    info["quoted"]["medias"] = await self._parse_media(quoted_media)
                info["quoted"]["full_text"] = unescape(quoted["result"]["legacy"].get('full_text'))
                info["quoted"]['author'] = {"username": "".join([x for x in username if x not in '\\/:*?"<>|()']), 
                                            "nick": eval(f"quoted{self._path_parser(self._find_key(quoted, 'name'))}"),
                                            "link": f'https://x.com/{username}',
                                            "avatar": None}
                attempt = self._find_key(quoted, 'profile_image_url_https')
                if attempt:
                    info['quoted']['author']['avatar'] = eval(f"quoted{self._path_parser(attempt)}")
                else:
                    info['quoted']['author']['avatar'] = eval(f"quoted{self._path_parser(self._find_key(quoted, 'image_url'))}")
                info["quoted"]['link'] = tweet_results['legacy'].get('quoted_status_permalink').get('expanded')
        elif reply := tweet_results['legacy'].get("in_reply_to_status_id_str"):
            info["replying_to"] = await self.download(f'https://x.com/{tweet_results["legacy"].get("in_reply_to_screen_name")}/status/{reply}', return_media_url=True)
        info["link"] = f"https://x.com/{info['author']['username']}/status/{tweet_results['legacy']['id_str']}"
        info["date_posted"] = datetime.strptime(tweet_results['legacy'].get('created_at'), "%a %b %d %H:%M:%S %z %Y").timestamp()
        info["bookmarks"] = tweet_results['legacy'].get("bookmark_count", 0)
        info["likes"] = tweet_results['legacy'].get("favorite_count", 0)
        info["quotes"] = tweet_results['legacy'].get("quote_count", 0)
        info["replies"] = tweet_results['legacy'].get("reply_count", 0)
        info["retweets"] = tweet_results['legacy'].get("retweet_count", 0)
        info["views"] = tweet_results['views'].get('count', 0)
        if tweet_results['legacy'].get("possibly_sensitive"):
            info["nsfw"] = True
        return info
    async def _get_guest_token(self):
        if os.path.exists("guesttoken.txt"):
            with open("guesttoken.txt", "r") as f1:
                a = f1.read().split("\t")
                guesttoken = a[0]
                expiry = a[1]
                if datetime.fromisoformat(expiry)>datetime.now():
                    return guesttoken
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.7',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Chromium";v="136", "Brave";v="136", "Not.A/Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        }
        pattern = r"document\.cookie=\"gt=(\d+);"
        async with self.session.get("https://x.com", headers=headers) as r:
            response = await r.text("utf8")
            if (match := re.search(pattern, response)):
                guesttoken = match.group(1)
                with open("guesttoken.txt", "w") as f1:
                    f1.write(f"{guesttoken}\t{(datetime.now()+timedelta(seconds=900)).isoformat()}")
                return guesttoken
        return None
    async def _get_api_url(self):
        
        if not hasattr(self, "jslink"):
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            async with self.session.get(self.link, headers=self.headers, ) as r:
                text = await r.text('utf-8')
                matches = re.search(pattern ,text)
            if not matches:
                await self._post_data()
                async with self.session.get(self.link, headers=self.headers, ) as r:
                    text = await r.text('utf-8')
                    matches = re.search(pattern ,text)
                    if not matches:
                        if os.path.exists("bearer_token.txt"):
                            os.remove("bearer_token.txt")
                            await self._post_data()
                            async with self.session.get(self.link, headers=self.headers, ) as r:
                                text = await r.text('utf-8')
                                matches = re.search(pattern ,text)
            self.jslink = matches.group(1)
        pattern2 = r'{queryId:\"(.*?)\",operationName:\"TweetResultByRestId\"'
        pattern3 = r'queryId:\"(.*?)\",operationName:\"TweetDetail\"'
        async with self.session.get(self.jslink, headers=self.headers, ) as r:
            js = await r.text()
        location1 = js[js.find("TweetResultByRestId")-50:js.find("TweetResultByRestId")+50]
        location2 = js[js.find("TweetDetail")-50:js.find("TweetDetail")+50]
        restid = re.search(pattern2, location1).group(1)
        tweetdetail = re.search(pattern3, location2).group(1)
        restid = f'https://api.x.com/graphql/{restid}/TweetResultByRestId'
        tweetdetail = f'https://x.com/i/api/graphql/{tweetdetail}/TweetDetail'
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
                # await self._post_data()
                headers = {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'accept-language': 'en-US,en;q=0.8',
                    'priority': 'u=0, i',
                    'referer': 'https://x.com/',
                    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'cross-site',
                    'sec-gpc': '1',
                    'upgrade-insecure-requests': '1',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                }
                link = self.link if hasattr(self, "link") else "https://x.com"
                
                async with self.session.get(link, headers=headers, params={"mx": 2}) as r:
                    pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
                    text = await r.text()
                    matches = re.search(pattern, text)
                    if not matches:
                        raise Exception("couldnt get bearer token javascript")
                self.jslink = matches.group(1)
                async with self.session.get(self.jslink, ) as r:
                    pattern = r'const e=\"(.*?)\";if\(!e\)throw new Error\(\"Bearer token'
                    while True:
                        chunk = await r.content.read(1024*10)
                        if not chunk:
                            break
                        matches = re.search(pattern, chunk.decode("utf-8"))
                        if matches:
                            break
                if not matches:
                    raise Exception(f"Couldn't find bearer token.")
                with open("bearer_token.txt", "w") as f1:
                    f1.write("Bearer " + matches.group(1))
                self.bearer = "Bearer " + matches.group(1)
                return matches
    async def _post_data(self):
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.8',
            'priority': 'u=0, i',
            'referer': 'https://x.com/',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'cross-site',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        async with self.session.get(self.link if hasattr(self, 'link') else 'https://x.com', headers=headers, ) as r:
            pattern_redirect = r"document\.location = \"(.*?)\"</script>"
            text = await r.text()
            matches = re.search(pattern_redirect, text).group(1)
            async with self.session.get(matches, headers=headers, ) as r:
                tok = r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />"
                text = await r.text()
                tok = re.search(r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />", text).group(1)
                data = re.search(r"<input type=\"hidden\" name=\"data\" value=\"(.*?)\" />", text).group(1)
                refresh = re.search(r"<meta http-equiv=\"refresh\" content=\"\d+; url = (.*?)\" />", text).group(1)
                payload = {"data": data, "tok": tok}
                url = re.search(r"<form action=\"(.*?)\"", text).group(1)
                async with self.session.post(url, data=json.dumps(payload), headers=headers, ) as r:
                    pass
                async with self.session.get(refresh, headers=headers, ) as r:
                    pass
class Grok(TwitterDownloader):
    def __init__(self, model: Literal['grok-3', 'grok-2'] = 'grok-2', img_gen_count: int = 4, *args):
        self.model = model
        self.img_gen_count = img_gen_count
        super().__init__(*args)
    async def __aenter__(self):
        self.data = {
            "responses": [
            ],
            "systemPromptName": "",
            "grokModelOptionId": self.model,
            "conversationId": None,
            "returnSearchResults": True,
            "returnCitations": True,
            "promptMetadata": {
                "promptSource": "NATURAL",
                "action": "INPUT"
            },
            "imageGenerationCount": 4,
            "requestFeatures": {
                "eagerTweets": True,
                "serverHistory": True
            },
            "enableSideBySide": True,
            "toolOverrides": {},
            "isDeepsearch": False,
            "isReasoning": False
            }
        self.started = False
        return self
    async def __aexit__(self, a, b, c):
        if a:
            print("".join(traceback.format_exception(a, b, c)))
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
            self.session = aiohttp.ClientSession(connector=self._give_connector(self.proxy), max_field_size=MAX_FIELD_SIZE)
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
            async with self.session.get("https://x.com/i/grok", headers=headers, cookies=self.cookies) as r:
                rtext = await r.text("utf-8")
            js_pattern = r"\"(shared~bundle\.(?:Grok~bundle\.)?ReaderMode~bundle\.Birdwatch~bundle\.TwitterArticles~bundle\.Compose~bundle\.Settings~b(?:.*?))\": ?\"(.*?)\""
            js_match = re.findall(js_pattern, rtext)
            base_url = "https://abs.twimg.com/responsive-web/client-web/"
            queryId = None
            for part_1, part_2 in js_match:
                async with self.session.get(base_url + part_1 + '.' + part_2 + "a" + ".js", ) as r:
                    js_text = await r.text("utf-8")
                queryId_pattern = r":\"(.*?)\",operationName:\"CreateGrokConversation\",.*?}}"
                js_text = js_text.split("queryId")
                for i in js_text:
                    if queryId:=re.search(queryId_pattern, i):
                        queryId = queryId.group(1)
                        break
                if queryId:
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
    async def add_response(self, message: str, file: str = None, deep_search: bool = False, reasoning:bool = False):
        if not self.started:
            raise Exception(f"Run start_chat() before adding a response. If manually using your own values, set the Grok object 'started' attribute to True")
        if not hasattr(self, "bearer"):
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
            self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.8',
            'authorization': self.bearer,
            'content-type': 'application/json',
            'origin': 'https://x.com',
            'priority': 'u=1, i',
            'referer': 'https://x.com',
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
        headers = {
            'sec-ch-ua-platform': '"Windows"',
            'authorization': self.bearer,
            'x-csrf-token': self.headers.get("x-csrf-token"),
            'Referer': 'https://x.com/',
            'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'x-twitter-client-language': 'en',
            'sec-ch-ua-mobile': '?0',
            'x-client-transaction-id': 'gUKiIbzVFKlQFRVuFixSiyAy801YTuw2mNPAWL1cdDwM6Gz2EyXkE1Nio7a/oeZbHdg7GYKl0oTf9quztoIZg8kHmxKMgg',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        }
        self.data["responses"].append({
                            "message":message,
                            "sender":1,
                            "promptSource":"",
                            "fileAttachments":[]
                        })
        self.data['isDeepsearch'] = deep_search
        self.data['isReasoning'] = reasoning
        if file:
            if not os.path.exists(file):
                if not file.startswith("http"):
                    raise FileNotFoundError(f"Couldn't find {file}")
                else:
                    async with self.session.get(file) as r:
                        accepted = ["image", "pdf", "json"]
                        proper = False
                        for i in accepted:
                            if i in r.headers.get("content-type").lower():
                                proper = True
                        if not proper: 
                            raise ValueError(f"File must be an image/pdf/json")
                        ext = mimetypes.guess_extension(r.headers.get("content-type"))
                        file = f"grok_file-{int(datetime.now().timestamp())}{ext}"
                        with open(file, "wb") as f1:
                            while True:
                                chunk = await r.content.read(1024)
                                if not chunk:
                                    break
                                f1.write(chunk)
            else:
                accepted = ["image", "pdf", "json"]
                proper = False
                for i in accepted:
                    if i in mimetypes.guess_type(file)[0].lower():
                        proper = True
                if not proper:
                    raise ValueError(f"File must be an image/pdf/json")
            data = aiohttp.FormData()
            data.add_field("image", open(file, 'rb'), content_type=mimetypes.guess_type(file)[0])
            _headers = {
                'sec-ch-ua-platform': '"Windows"',
                'x-csrf-token': self.headers.get("x-csrf-token"),
                'authorization': self.bearer,
                'Referer': 'https://x.com/i/grok',
                'x-client-transaction-id': 'gUKiIbzVFKlQFRVuFixSiyAy801YTuw2mNPAWL1cdDwM6Gz2EyXkE1Nio7a/oeZbHdg7GYKl0oTf9quztoIZg8kHmxKMgg',
                'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'x-twitter-client-language': 'en',
                'sec-ch-ua-mobile': '?0',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            }
            async with self.session.post("https://grok.x.com/2/grok/attachment.json", headers=_headers, cookies=self.cookies, data=data) as r:
                response = await r.json()
                if self.debug:
                    print(response)
                self.data["responses"][-1]["fileAttachments"] += response
        finished = {}
        if self.debug:
            print("sending:")
            print(self.data)
        async with self.session.post('https://grok.x.com/2/grok/add_response.json', headers=headers, data=json.dumps(self.data), cookies=self.cookies) as r:
            if self.debug:
                print("sent headers:")
                temp_head = {}
                for key, value in r.request_info.headers.items():
                    temp_head[key] = value
                print(temp_head)
            result = ""
            # json_results = []
            cited = None
            temp = bytearray()
            start, end = None, None
            thinking = ""
            images = []
            while True:
                chunk = await r.content.read(1)
                if not chunk:
                    break
                temp += chunk
                try:
                    a = json.loads(temp)
                    if self.debug:
                        print(a)
                    if a.get("result") and a['result'].get("message"):
                        if not a['result'].get('isThinking') and a['result'].get("messageStepId", "final") == "final":
                            result += a['result']['message']
                        else:
                            thinking += a['result']['message']
                            if not start:
                                start = datetime.now()
                    elif a.get("result") and a['result'].get("imageAttachment"):
                        images.append(a['result']['imageAttachment'])
                    if a.get("result") and a['result'].get("citedWebResults"):
                        cited = a['result']["citedWebResults"]
                    # json_results.append(a)
                    temp = bytearray()
                except:
                    continue
            
            if start:
                end = datetime.now()
                finished['thinking_time'] = (end-start).seconds
                finished["thinking"] = thinking
            # for i in json_results:
            #     if i.get("result") and i['result'].get("message"):
            #         result += i['result']['message']
            #     elif i.get('result') and i['result'].get("imageAttachment"):
            #         images.append(i['result']['imageAttachment'])
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
            finished["citedWebResults"] = cited
            finished["message"] = result
            return finished
async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("link", help="link to twitter post")
    parser.add_argument("-m", "--max-size", type=float, help="max size in mb of a video")
    parser.add_argument("-r", "--return-url", action="store_true", help="returns urls of medias instead of download", default=False)
    parser.add_argument("-p", "--proxy", type=str, help="https/socks proxy to use")
    parser.add_argument("-d", "--dash",default=False, action="store_true", help="download dash video format instead of direct")
    parser.add_argument("-c", "--caption", action="store_true", help="burn in twitter given captions into the video")
    parser.add_argument("-dbg", "--debug", action="store_true", help="debug settings")
    args = parser.parse_args()
    downloader = TwitterDownloader(args.proxy, args.debug)
    result = await downloader.download(link = args.link, max_size=args.max_size, return_media_url=args.return_url,video_format= "dash" if args.dash else "direct",caption_videos= args.caption)
    print(json.dumps(result, indent=4, ensure_ascii=False))
async def chatting():
    """example function to chat with grok in console"""
    a = '\n'
    async with Grok(model='grok-3') as grok:
        await grok.start_chat()
        print("conversation id:", grok.conversation_id,)
        deepsearch = False
        reasoning = False
        while True:
            you = str(input(f"{'[deepsearch]' if deepsearch else ''}{'[reasoning]' if reasoning else ''}QUERY: "))
            if you == "deepsearch":
                deepsearch = True
                continue
            if you == "reasoning":
                reasoning = True
                continue
            response = await grok.add_response(you, deep_search=deepsearch, reasoning=reasoning)
            deepsearch = False
            reasoning = False
            print("GROK: " + response['message'])
            if response.get('images'):
                print(f"Following images have been generated:{a}{a.join([x.get('fileName') for x in response.get('images')])}")
            if response.get("thinking"):
                print(f"Grok thought for {response.get('thinking_time')} seconds")
                print("Grok thought: ")
                print(response.get("thinking"))
if __name__ == "__main__":
    asyncio.run(main())