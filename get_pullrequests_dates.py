import requests
import json
import os
import sys
from datetime import datetime


def build_request_url(user: str, repo: str, page: int, per_page=100):
    return "https://api.github.com/repos/" + user + "/" + repo + \
           "/pulls?state=all&per_page=" + str(per_page) + "&page=" + str(page)


def json_fname(name: str):
    return name + ".json"


def format_json_response(string: str, page=-1):
    if page == 1:
        return string[:-2] + ",\n"
    elif page == -1:
        return string[2:] + "\n]"
    else:
        return string[2:-2]


def fetch_pull_requests(user: str, token: str, repo: str):
    output_file = open(json_fname(repo), "w")
    page = 1

    while True:
        response = requests.get(build_request_url(user, repo, page), auth=(user, token))
        response_json = response.json()
        response_json_string = json.dumps(response_json, sort_keys=True, indent=4)
        print("[ II ] url: " + build_request_url(user, repo, page))
        print(response_json_string)

        if not response_json:
            response_json_string = format_json_response(response_json_string)
            output_file.write(response_json_string)
            break
        output_file.write(format_json_response(response_json_string, page))
        page += 1

    output_file.close()
    print(f"[ II ] Data from {repo} from {page - 1} pages cached")


def main():
    # Get credits
    user = input("GitHub user: ")
    token = input("GitHub access token: ")

    repo_names = ["spbetu_os_2020_8381"]#, "spbetu_os_2020_8382", "spbetu_os_2020_8383"]

    #for repo in repo_names:
    #    #check cache
    #    if not os.path.isfile(json_fname(repo)) or input(f"Cache for '{repo}' is exists. Reload? [N/y]: ") == "y":
    #        fetch_pull_requests(user, token, repo)

    for repo in repo_names:
        repo_file = open(json_fname(repo), "r")
        repo_json = json.load(repo_file)

        repo_file.close()
        print(repo_json[2])
        for pr in repo_json:
            created_date = datetime.fromisoformat(pr["created_at"][:-1]).strftime("%d.%m")
            if pr["state"] == "closed":
                closed_date = datetime.fromisoformat(pr["closed_at"][:-1]).strftime("%d.%m")
            else:
                closed_date = "X"
            number = pr["number"]
            author_github = pr["user"]["login"]
            title = pr["title"]
            print(f"{number}\t{author_github}\t{title}\t{created_date} -- {closed_date}\n")
    print("Success!")


if __name__ == "__main__":
    sys.exit(main())



