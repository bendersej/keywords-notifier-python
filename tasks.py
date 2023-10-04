import re
import requests
import json
import os
from robocorp import workitems
from robocorp.tasks import task
from robocorp import vault
from robocorp import storage


def clean_list(keyword_content):
    keyword_content_list = keyword_content.strip().split("\n")
    trimmed_list = [string.strip() for string in keyword_content_list]
    cleaned_list = [string for string in trimmed_list if string]
    return cleaned_list


@task
def send_notification():
    item = workitems.inputs.current
    emailContent = item.payload["email"]["text"]

    pattern = r"F5Bot found something!\n\n(.*?)\n\nDo you have comments or suggestions about F5Bot?"
    match = re.search(pattern, emailContent, re.DOTALL)

    if not match:
        return

    subreddits_to_ignore = clean_list(storage.get_text("mentions_black_list"))

    keyword_content = match.group(1)
    keyword, title, url = clean_list(keyword_content)

    secret = vault.get_secret("SlackNotifier")
    slack_webhook = secret["WEBHOOK"]
    headers = {"Content-type": "application/json"}

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join([f"*{keyword}*", f"_{title}_"]),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": url,
                    },
                ],
            },
        ],
        "channel": os.getenv("SLACK_CHANNEL"),
    }

    if any(subreddit in url for subreddit in subreddits_to_ignore):
        print(
            f"Not posting the mention: {url} is included in the list of subreddits to ignore."
        )
        print("Subreddits to ignore", subreddits_to_ignore)
        return

    response = requests.post(slack_webhook, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        print("Message posted successfully.")
    else:
        print(f"Failed to post message: {response.content}")
