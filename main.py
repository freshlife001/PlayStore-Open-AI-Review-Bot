import openai
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

app_package_name = config["app_package_name"]
key_file = config["key_file"]
openai.api_key = config["openai_key"]
openai.api_base = config["openai_base"]
dry_run = config["dry_run"]
pre_prompt = config["pre_prompt"]
user_prompt = config["user_prompt"]

# httplib2.debuglevel = 1

def get_last_week_reviews():
    credentials = service_account.Credentials.from_service_account_file(
        key_file, scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )

    try:
        service = build("androidpublisher", "v3", credentials=credentials)
        response = (
            service.reviews()
            .list(
                packageName=app_package_name,
            )
            .execute()
        )
        all_reviews = response.get("reviews", [])

        return all_reviews

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []


def get_openai_response(review_text, starts, authorName):
    messages = [
        {"role": "system", "content": pre_prompt},
        {"role": "user",
         "content": f"A user left a review for our app: '{review_text}' with '{starts}/5 stars, and the author is named '{authorName}''\n" + user_prompt
         }
    ]

    try:
        response = openai.ChatCompletion.create(
            model="deepseek-chat",
            temperature=0.7,
            stream=False,
            messages=messages
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def reply_to_review(review_id, reply_text):
    if dry_run:
        return
    credentials = service_account.Credentials.from_service_account_file(
        key_file, scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )

    try:
        service = build("androidpublisher", "v3", credentials=credentials)
        response = (
            service.reviews()
            .reply(packageName=app_package_name, reviewId=review_id, body={"replyText": reply_text})
            .execute()
        )
        return response
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


if __name__ == "__main__":

    try:
        last_x_reviews = get_last_week_reviews()
        print(f"Last reviews for {app_package_name}:")
        for i, review in enumerate(last_x_reviews, 1):
            reviewId = review["reviewId"]
            authorName = review["authorName"]
            comment = review["comments"][0]["userComment"]
            stars = comment["starRating"]
            if len(review["comments"]) == 1:
                print(f"{i}. {comment['text']} (Rating: {comment['starRating']})")
                response = get_openai_response(comment["text"], stars, authorName)
                print(f"Response: {response}")
                reply_to_review(reviewId, response)
            else:
                print(f"{i}. {comment['text']} (Rating: {comment['starRating']})")
                for reply in review["comments"][1:]:
                    print(f" >> {reply['developerComment']['text']}")
    except Exception as e:
        print(str(e))
