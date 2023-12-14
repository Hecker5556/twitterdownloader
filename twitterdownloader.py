import aiohttp, aiofiles, asyncio, re, datetime, os
from tqdm.asyncio import tqdm
from datetime import datetime

class twitterdownloader:
    class invalidlink(Exception):
        def __init__(self, *args: object) -> None:
            super().__init__(*args)

    async def get_guest_token(session: aiohttp.ClientSession, headers: dict) -> str:
        async with session.post('https://api.twitter.com/1.1/guest/activate.json', headers=headers) as r:
            a = await r.json()
            return a['guest_token']
        
    async def get_bearer_token(session: aiohttp.ClientSession, link: str, headers: dict) -> str:
        async with session.get(link, headers=headers) as r:
            pattern = r'href=\"(https://abs\.twimg\.com/responsive-web/client-web/main\.(?:.*?)\.js)\"'
            text = await r.text()
            matches = re.findall(pattern, text)
            if not matches:
                raise twitterdownloader.invalidlink("invalid link idk")
        jslink = matches[0]
        async with session.get(jslink) as r:
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
    
    async def downloader(link: str, filename: str, session: aiohttp.ClientSession):
        async with aiofiles.open(filename, 'wb') as f1:
            async with session.get(link) as r:
                total = int(r.headers.get('content-length'))
                progress = tqdm(total=total, unit='iB', unit_scale=True)
                while True:
                    chunk = await r.content.read(1024)
                    if not chunk:
                        break
                    await f1.write(chunk)
                    progress.update(len(chunk))
                progress.close()
    async def download(link: str, maxsize: int = None, returnurl: bool = False):
        link = link.split('?')[0]
        pattern = r'https://(?:x)?(?:twitter)?\.com/(?:.*?)/status/(\d*?)$'
        tweet_id = re.findall(pattern, link)
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
            'features': '{"creator_subscriptions_tweet_preview_api_enabled":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"tweetypie_unmention_optimization_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":false,"tweet_awards_web_tipping_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"responsive_web_media_download_video_enabled":false,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_enhance_cards_enabled":false}',
        }
        apiurl = 'https://api.twitter.com/graphql/0M7XkziVtEOeOk9UyiKo9A/TweetResultByRestId'
        async with aiohttp.ClientSession() as session:
            if not os.path.exists("bearer_token.txt"):
                bearer = await twitterdownloader.get_bearer_token(session, link, headers)
            else:
                async with aiofiles.open("bearer_token.txt", "r") as f1:
                    bearer = await f1.read()
            headers['authorization'] = bearer
            guestoken = await twitterdownloader.get_guest_token(session, headers)
            cookies = {
                'gt': guestoken
            }
            headers['x-guest-token'] = guestoken
            async with session.get(apiurl, cookies=cookies, headers=headers, params=params) as r:
                a = await r.json()
            medias = a["data"]["tweetResult"]["result"]["legacy"]["entities"]["media"]
            fulltext = a["data"]["tweetResult"]["result"]["legacy"].get('full_text')
            author = "".join([x for x in a["data"]["tweetResult"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"] if x not in '\\/:*?"<>|()'])
            if fulltext:
                fulltext = fulltext.encode('utf-16', 'surrogatepass').decode('utf-16')
            media_urls = []
            for media in medias:
                if media.get("video_info"):
                    videos = []
                    for variant in media["video_info"]["variants"]:
                        videos.append(variant["url"])
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
                            if ".m3u8?tag=" in video:
                                continue
                            async with session.get(video, headers=headers) as r:
                                print(video)
                                sizes[index] = r.headers.get('content-length')
                        if len(media) == 1:
                            await twitterdownloader.downloader(media[0], filename, session)
                            continue
                        sizes = sorted(sizes.items(), key=lambda x: int(x[1]), reverse=True)
                        for index, size in sizes:
                            if int(size)/(1024*1024) < maxsize:
                                filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                                filenames.append(filename)
                                await twitterdownloader.downloader(media[index], filename, session)
                                break
                    else:
                        filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.mp4'
                        filenames.append(filename)
                        if len(media) == 1:
                            await twitterdownloader.downloader(media[0], filename, session)
                            continue
                        resolutions = {}
                        pattern = r'((?:\d*?)x(?:\d*?))/'
                        for index, video in enumerate(media):
                            matches = re.findall(pattern, video)
                            if not matches:
                                continue
                            uh = 1
                            the = [int(x) for x in matches[0].split("x")]
                            for i in the:
                                uh = uh * i
                            resolutions[index] = uh
                        resolutions = sorted(resolutions.items(), key=lambda x: x[1], reverse=True)
                        await twitterdownloader.downloader(media[resolutions[0][0]], filename, session)
                else:
                    filename = f'{author}-{round(datetime.now().timestamp())}-{mindex}.jpg'
                    filenames.append(filename)
                    await twitterdownloader.downloader(media, filename, session)
            return {"filenames": filenames, "author": author, "caption": fulltext}
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("link", help="link to twitter post")
    parser.add_argument("-m", "--max-size", type=int, help="max size in mb of a video")
    parser.add_argument("-r", "--return-url", action="store_true", help="print urls of medias instead of download")
    args = parser.parse_args()
    print(asyncio.run(twitterdownloader.download(args.link, args.max_size, args.return_url)))