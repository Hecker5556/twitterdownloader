from .twitterdownloader import Grok
import asyncio
import argparse
import os
import json
async def chatting(guest_id, auth_token, csrf):
    """example function to chat with grok in console"""
    a = '\n'
    async with Grok(guest_id, auth_token, csrf) as grok:
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
            if you == "id":
                grok.conversation_id = str(input("conversation id: "))
                grok.data = Grok.data
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
def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("credentials", help="Location containing credentials in JSON format, more on README.md")
    args = argparser.parse_args()
    if os.path.exists(args.credentials) is False:
        raise FileNotFoundError(f"Couldn't find credentials file")
    with open(args.credentials, "r") as f1:
        creds = json.load(f1)
    if (creds.get('guest_id') is None) or (creds.get('auth_token') is None) or (creds.get('csrf') is None):
        raise Exception(f"Credentials missing! Required: guest_id, auth_token, csrf, check README.md")
    try:
        asyncio.run(chatting(creds.get('guest_id'), creds.get('auth_token'), creds.get('csrf')))
    except KeyboardInterrupt:
        print("Exiting...")
if __name__ == "__main__":
    main()