import aiohttp, aiofiles, asyncio, re, datetime, os, json
from tqdm.asyncio import tqdm
from datetime import datetime
from aiohttp_socks import ProxyConnector
from html import unescape
from emoji import emojize
from datetime import datetime
if not os.path.exists('features.json'):
    with open('features.json', 'w') as f1:
        f1.write("""{"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":false,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_media_download_video_enabled":false,"responsive_web_enhance_cards_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"tweet_with_visibility_results_prefer_gql_media_interstitial_enabled":true,"rweb_tipjar_consumption_enabled":true, "creator_subscriptions_quote_tweet_preview_enabled":true, "rweb_tipjar_consumption_enabled": true, "creator_subscriptions_quote_tweet_preview_enabled": true}""")
with open("features.json", "r") as f1:
    FEATURES = json.load(f1)
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
    async def get_guest_token(self, session: aiohttp.ClientSession, headers: dict, proxy: str = None) -> str:
        async with session.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            a = await r.json()
            return a['guest_token']
    def createconnector(self, proxy: str):
        return aiohttp.TCPConnector() if (not proxy or proxy and proxy.startswith("sock")) else ProxyConnector.from_url(proxy)
    async def get_api_url(self, session: aiohttp.ClientSession, link: str, headers: dict, proxy: str = None) -> tuple[str, str]:
        if not hasattr(self, "jslink"):
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                text = await r.text('utf-8')
                matches = re.findall(pattern ,text)
            if not matches:
                await self._post_data(session, link, headers, proxy)
                async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                    text = await r.text('utf-8')
                    matches = re.findall(pattern ,text)
            jslink = matches[0]
        else:
            jslink = self.jslink
        pattern2 = r'{queryId:\"(.*?)\",operationName:\"TweetResultByRestId\"'
        pattern3 = r'queryId:\"(.*?)\",operationName:\"TweetDetail\"'
        async with session.get(jslink, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
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
    async def _post_data(self, session: aiohttp.ClientSession, link: str, headers: dict, proxy: str = None):
        async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            pattern_redirect = r"document\.location = \"(.*?)\"</script>"
            text = await r.text()
            matches = re.findall(pattern_redirect, text)[0]
            async with session.get(matches, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                tok = r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />"
                text = await r.text()
                tok = re.findall(r"<input type=\"hidden\" name=\"tok\" value=\"(.*?)\" />", text)[0]
                data = re.findall(r"<input type=\"hidden\" name=\"data\" value=\"(.*?)\" />", text)[0]
                refresh = re.findall(r"<meta http-equiv=\"refresh\" content=\"5; url = (.*?)\" />", text)[0]
                payload = {"data": data, "tok": tok}
                url = re.findall(r"<form action=\"(.*?)\"", text)[0]
                async with session.post(url, data=json.dumps(payload), headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                    pass
                async with session.get(refresh, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                    pass
    async def get_bearer_token(self, session: aiohttp.ClientSession, link: str, headers: dict, proxy: str = None) -> str:
        await self._post_data(session, link, headers, proxy)
        async with session.get(link, headers=headers, proxy=proxy if proxy and proxy.startswith("https") else None, params={"mx": 2}) as r:
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            text = await r.text()
            matches = re.findall(pattern, text)
            if not matches:
                raise self.invalidlink("couldnt get bearer token javascript")
        jslink = matches[0]
        self.jslink = jslink
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
            raise self.invalidlink("invalid link idk")
        async with aiofiles.open("bearer_token.txt", "w") as f1:
            await f1.write(matches[0])
        return matches[0]
    async def get_authenticated_tweet(self, tweet_id: int, csrf: str, guest_id: str, auth_token: str, bearer_token: str, session: aiohttp.ClientSession, apiurl: str, proxy: str = None):
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
            'features': json.dumps(FEATURES),
            'fieldToggles': '{"withArticleRichContentState":false}',
        }
        async with session.get(apiurl, cookies=cookies, headers=headers, params=params, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
            result = await r.json()
            with open("response.json", "w") as f1:
                json.dump(result, f1, indent=4)
        for i in result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][::-1]:
            if "tweet" in i.get("entryId"):
                entry = i
                break
        # entry = result["data"]["threaded_conversation_with_injections_v2"]["instructions"][0]["entries"][-1]
        resp_type = False if entry["content"].get("items") else True
        if not resp_type:
            tweet_results = entry["content"]["items"][0]["item"]["itemContent"]["tweet_results"]["result"]
        else:
            tweet_results = entry["content"]["itemContent"]["tweet_results"]["result"]
        medias = tweet_results["legacy"]["entities"].get("media")
        author = tweet_results["core"]["user_results"]["result"]["legacy"]["screen_name"]
        author = "".join([x for x in author if x not in '\\/:*?"<>|()'])
        fulltext = tweet_results["legacy"]["full_text"]
        quoted  = tweet_results.get("quoted_status_result")
        quoted_tweet = {}
        if quoted:
            q_media = quoted["result"]["legacy"]["entities"].get("media")
            if q_media:
                quoted_tweet['media'] = [x.get('media_url_https') for x in q_media]
            quoted_tweet['caption'] = quoted["result"]["legacy"].get('full_text')
            quoted_tweet['author'] = "".join([x for x in quoted["result"]["core"]["user_results"]])
            quoted_tweet['link'] = tweet_results['legacy'].get('quoted_status_permalink').get('expanded')
        reply = tweet_results['legacy'].get("in_reply_to_status_id_str")
        replyingto = {}
        if reply:
            replyingto = await self.download(f'https://x.com/{tweet_results["legacy"].get("in_reply_to_screen_name")}/status/{reply}', returnurl=True, proxy=proxy)
        link = f"https://x.com/{author}/status/{tweet_results['legacy']['id_str']}"
        date_posted = datetime.strptime(tweet_results['legacy'].get('created_at'), "%a %b %d %H:%M:%S %z %Y").timestamp()
        bookmark_count = tweet_results['legacy'].get("bookmark_count")
        likes = tweet_results['legacy'].get("favorite_count")
        times_quoted = tweet_results['legacy'].get("quote_count")
        times_replied = tweet_results['legacy'].get("reply_count")
        times_retweeted = tweet_results['legacy'].get("retweet_count")
        author_link = f'https://x.com/{tweet_results["core"]["user_results"]["result"]["legacy"]["screen_name"]}'
        views = tweet_results['views']['count']
        profile_picture = tweet_results['core']['user_results']['result']['legacy'].get('profile_image_url_https')
        return medias, author, fulltext, quoted_tweet, replyingto, link, date_posted, bookmark_count, likes, times_quoted, times_replied, times_retweeted, author_link, views, profile_picture
    async def downloader(self, link: str, filename: str, session: aiohttp.ClientSession, proxy: str = None):
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
    async def download(self, link: str, maxsize: int = None, returnurl: bool = False, proxy: str = None):
        link = link.split('?')[0]
        pattern = r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/?$'
        pattern2 = r"https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)/(?:.*?)/\d$"
        tweet_id = re.findall(pattern, link)
        if not tweet_id:
            tweet_id = re.findall(pattern2, link)
            if not tweet_id:
                raise self.invalidlink("the link is invalid i think")
        
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
            'features': json.dumps(FEATURES)
        }
        async with aiohttp.ClientSession(connector=self.createconnector(proxy)) as session:
            if not os.path.exists("bearer_token.txt"):
                bearer = await self.get_bearer_token(session, link, headers, proxy)
            else:
                async with aiofiles.open("bearer_token.txt", "r") as f1:
                    bearer = await f1.read()
            if not os.path.exists("apiurls.json"):
                restid, tweetdetail = await self.get_api_url(session, link, headers, proxy)
            else:
                async with aiofiles.open("apiurls.json", "r") as f1:
                    thejson = await f1.read()
                    thejson = json.loads(thejson)
                    restid, tweetdetail = thejson["restid"], thejson["tweetdetail"]
            headers['authorization'] = bearer
            guestoken = await self.get_guest_token(session, headers, proxy)
            cookies = {
                'gt': guestoken
            }
            headers['x-guest-token'] = guestoken
            async with session.get(restid, cookies=cookies, headers=headers, params=params, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                a = await r.json()
                async with aiofiles.open("response.json", "w") as f1:
                    await f1.write(json.dumps(a))
            if not a.get('data'):
                new_features = a['errors'][0]['message'].split(': ')[1].split(', ')
                for ft in new_features:
                    print(f"adding new feature {ft} to features")
                    FEATURES[ft] = True
                with open('features.json', 'w') as f1:
                    json.dump(FEATURES, f1)
                params = {
                    'variables': '{"tweetId":%s,"withCommunity":false,"includePromotedContent":false,"withVoice":false}' % tweet_id,
                    'features': json.dumps(FEATURES)
                }
                async with session.get(restid, cookies=cookies, headers=headers, params=params, proxy=proxy if proxy and proxy.startswith("https") else None) as r:
                    a = await r.json()
                    async with aiofiles.open("response.json", "w") as f1:
                        await f1.write(json.dumps(a))    
            replyingto = None
            is_nsfw = False
            if a["data"]["tweetResult"]["result"].get("__typename") and a["data"]["tweetResult"]["result"].get("__typename") == "TweetUnavailable":
                if not os.path.exists("env.py"):
                    raise self.missingcredentials("no credentials detected, make an env.py file, put csrf token, guest_id, auth_token there")
                from env import csrf, auth_token, guest_id
                result = await self.get_authenticated_tweet(tweet_id, csrf, guest_id, auth_token, bearer, session, tweetdetail, proxy)
                medias = result[0]
                fulltext = result[2]
                author = result[1]
                quoted_tweet = result[3]
                replyingto = result[4]
                is_nsfw = True
                original_link = result[5]
                date_posted = result[6]
                bookmark_count = result[7]
                likes = result[8]
                times_quoted = result[9]
                times_replied = result[10]
                times_retweeted = result[11]
                author_link = result[12]
                views = result[13]
                profile_picture = result[14]
            else:
                medias = a["data"]["tweetResult"]["result"]["legacy"]["entities"].get("media")
                if notetweet := a["data"]["tweetResult"]["result"].get("note_tweet"):
                    fulltext = notetweet['note_tweet_results']['result'].get("text")
                else:
                    fulltext = a["data"]["tweetResult"]["result"]["legacy"].get('full_text')
                author = "".join([x for x in a["data"]["tweetResult"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()'])
                quoted = a["data"]["tweetResult"]["result"].get("quoted_status_result")
                quoted_tweet = {}
                if quoted:
                    q_media = quoted["result"]["legacy"]["entities"].get("media")
                    if q_media:
                        quoted_tweet['media'] = [x.get('media_url_https') for x in q_media]
                    quoted_tweet['caption'] = quoted["result"]["legacy"].get('full_text')
                    quoted_tweet['author'] = "".join([x for x in quoted["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()'])
                    quoted_tweet['link'] = a["data"]["tweetResult"]["result"]['legacy'].get('quoted_status_permalink').get('expanded')
                replying_to = a["data"]["tweetResult"]["result"]["legacy"].get("in_reply_to_status_id_str")
                replyingto = {}
                if replying_to:
                    replyingto = await self.download(f'https://x.com/{a["data"]["tweetResult"]["result"]["legacy"].get("in_reply_to_screen_name")}/status/{replying_to}', returnurl=True, proxy=proxy)
                original_link = f'https://x.com/{author}/status/{a["data"]["tweetResult"]["result"]["legacy"].get("id_str")}'
                date_posted = datetime.strptime(a["data"]["tweetResult"]["result"]["legacy"].get('created_at'), "%a %b %d %H:%M:%S %z %Y").timestamp()
                bookmark_count = a["data"]["tweetResult"]["result"]["legacy"].get("bookmark_count")
                likes = a["data"]["tweetResult"]["result"]["legacy"].get("favorite_count")
                times_quoted = a["data"]["tweetResult"]["result"]["legacy"].get("quote_count")
                times_replied = a["data"]["tweetResult"]["result"]["legacy"].get("reply_count")
                times_retweeted = a["data"]["tweetResult"]["result"]["legacy"].get("retweet_count")
                author_link = f'https://x.com/{a["data"]["tweetResult"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"]}'
                views = a["data"]["tweetResult"]["result"]['views'].get('count')
                profile_picture = a["data"]["tweetResult"]["result"]["core"]["user_results"]["result"]["legacy"].get('profile_image_url_https')
            if fulltext:
                fulltext = emojize(unescape(fulltext)).encode('utf-16', 'surrogatepass').decode('utf-16')
            if not medias:
                print("no medias found")
                return {"caption": fulltext, "author": author, "quoted_tweet": quoted_tweet, 
                        "replying_to": replyingto, "is_nsfw": is_nsfw, "original_link": original_link,
                        "date_posted": date_posted, "bookmark_count": bookmark_count, "likes": likes,
                        "times_quoted": times_quoted, "times_replied": times_replied, "times_retweeted": times_retweeted,
                        "author_link": author_link, "views": views, "profile_picture": profile_picture}
            media_urls = []
            duration = 0
            img = None
            for media in medias:
                if media.get('type') == 'animated_gif':
                    media_urls.append((media['video_info']['variants'][0].get('url'), 0))
                elif media.get("video_info"):
                    duration = media["video_info"].get("duration_millis")
                    videos = []
                    for variant in media["video_info"]["variants"]:
                        videos.append((variant["url"], variant.get('bitrate')))
                    media_urls.append(videos)
                elif media.get('type') == 'photo':
                    media_urls.append(media.get("media_url_https"))
                if media.get("media_url_https"):
                    img = media.get("media_url_https")
            if returnurl:
                return {"mediaurls": media_urls, "author": author, "caption": fulltext, "quoted_tweet": quoted_tweet, "replying_to": replyingto, "image": img, "is_nsfw": is_nsfw, "original_link": original_link,
                        "date_posted": date_posted, "bookmark_count": bookmark_count, "likes": likes,
                        "times_quoted": times_quoted, "times_replied": times_replied, "times_retweeted": times_retweeted,
                        "author_link": author_link, "views": views}
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
                            await self.downloader(media[0], filename, session, proxy)
                            continue
                        sizes = sorted(sizes.items(), key=lambda x: float(x[1]), reverse=True)
                        downloaded = False
                        for index, size in sizes:
                            if size < maxsize:
                                filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                                filenames.append(filename)
                                # print(media[index][0])
                                await self.downloader(media[index][0], filename, session, proxy)
                                downloaded = True
                                break
                        if not downloaded:
                            raise self.videotoobig("video too large to download")
                    else:
                        filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                        filenames.append(filename)
                        if len(media) == 1:
                            await self.downloader(media[0], filename, session, proxy)
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
                        await self.downloader(media[resolutions[0][0]][0], filename, session, proxy)
                elif isinstance(media, tuple):
                    filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                    filenames.append(filename)
                    await self.downloader(media[0], filename, session, proxy)
                else:
                    filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.jpg'
                    filenames.append(filename)
                    await self.downloader(media, filename, session, proxy)
            return {"filenames": filenames, "author": author, "caption": fulltext, "quoted_tweet": quoted_tweet, "replying_to": replyingto, "image": img, "is_nsfw": is_nsfw, "original_link": original_link,
                        "date_posted": date_posted, "bookmark_count": bookmark_count, "likes": likes,
                        "times_quoted": times_quoted, "times_replied": times_replied, "times_retweeted": times_retweeted,
                        "author_link": author_link, "views": views, "profile_picture": profile_picture}
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("link", help="link to twitter post")
    parser.add_argument("-m", "--max-size", type=int, help="max size in mb of a video")
    parser.add_argument("-r", "--return-url", action="store_true", help="print urls of medias instead of download")
    parser.add_argument("-p", "--proxy", type=str, help="https/socks proxy to use")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(twitterdownloader().download(args.link, args.max_size, args.return_url, args.proxy)), indent=4, ensure_ascii=False))