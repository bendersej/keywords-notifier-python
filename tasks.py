import re
import requests
import json
import os
from robocorp import workitems
from robocorp.tasks import task
from robocorp import vault
from robocorp import storage
from bs4 import BeautifulSoup


def clean_list(list_of_strings):
    keyword_content_list = list_of_strings.strip().split("\n")
    trimmed_list = [string.strip() for string in keyword_content_list]
    cleaned_list = [string for string in trimmed_list if string]
    return cleaned_list


def get_keywords(keyword_content):
    # Dict<keyword, { url: string; title: string }[]>
    keywords = {}
    current_keyword = ""
    cleaned_list = clean_list(keyword_content)

    keyword_regex = r'Keyword: "(.*?)"'

    for item in cleaned_list:
        keyword_match = re.search(keyword_regex, item)

        if keyword_match:
            keyword = keyword_match.group(1)
            current_keyword = keyword
            keywords[current_keyword] = []
        else:
            key_type = "url" if item.startswith("http") else "title"

            existing_keyword_details = keywords[current_keyword]

            if (
                len(existing_keyword_details) == 0
                or len(existing_keyword_details[-1]) == 2
            ):
                existing_keyword_details.append({key_type: item})

            if len(existing_keyword_details[-1]) < 2:
                existing_keyword_details[-1][key_type] = item

    return keywords


@task
def send_notification():
    item = workitems.inputs.current
    emailContent = item.payload["email"]["text"]
    emailHTML = item.email().html
    soup = BeautifulSoup(emailHTML)

    comments = soup.find_all("span")

    pattern = r"F5Bot found something!\n\n(.*?)\n\nDo you have comments or suggestions about F5Bot?"
    match = re.search(pattern, emailContent, re.DOTALL)

    if not match:
        return

    subreddits_to_ignore = clean_list(storage.get_text("mentions_black_list"))

    keyword_content = match.group(1)

    keywords = get_keywords(keyword_content)

    secret = vault.get_secret("SlackNotifier")
    slack_webhook = secret["WEBHOOK"]
    headers = {"Content-type": "application/json"}

    for keyword in keywords:
        mention_idx = 0
        blocks = []

        for mention in keywords[keyword]:
            title = mention["title"]
            url = mention["url"].replace("www.reddit.com", "old.reddit.com")
            comment = comments[mention_idx].getText()
            print(comment)
            mention_idx += 1

            if any(subreddit in url for subreddit in subreddits_to_ignore):
                print(
                    f"Not posting the mention: {url} is included in the list of subreddits to ignore."
                )
                print("Subreddits to ignore", subreddits_to_ignore)
                continue

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(
                            [f"*Keyword: `{keyword}`*", f"_{title}_", f">{comment}"]
                        ),
                    },
                },
            )
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": url,
                        },
                    ],
                },
            )

        payload = {
            "blocks": blocks,
            "channel": os.getenv("SLACK_CHANNEL"),
        }

        response = requests.post(
            slack_webhook, headers=headers, data=json.dumps(payload)
        )

        if response.status_code == 200:
            print("Message posted successfully.")
        else:
            print(f"Failed to post message: {response.content}")
