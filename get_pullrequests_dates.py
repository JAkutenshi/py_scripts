import requests
import json
import re
import sys
import csv
import os
from datetime import datetime
from functools import reduce
from collections import defaultdict


def build_request_url(user: str, repo: str, page: int, per_page=100):
    return "https://api.github.com/repos/" + user + "/" + repo + \
           "/pulls?state=all&per_page=" + str(per_page) + "&page=" + str(page)


def json_fname(name: str):
    return name + ".json"


def load_json(fname: str):
    file = open(fname, "r")
    json_data = json.load(file)
    file.close()
    return json_data


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

        if not response_json:
            response_json_string = format_json_response(response_json_string)
            output_file.write(response_json_string)
            break
        output_file.write(format_json_response(response_json_string, page))
        page += 1

    output_file.close()
    print(f"[ II ] Data from {repo} from {page - 1} pages cached")


def is_valid_title(title: str, pr_num: int):
    if re.match(r"^\[(ACCEPT|CLOSED|WIP|READY|BADPR)\]\s+\w+\s+lab([1-7])$", title):
        return True
    elif re.match(r"^\[(ACCEPT|CLOSED|WIP|READY|BADPR|BAD_PR)\].*([1-7])$", title):
        print(f"[ WW ] Broken data in PR#{pr_num}, weak accept")
        return True
    else:
        print(f"[ EE ] Broken data in PR#{pr_num}, reject '{title}'")
        return False


def get_status_from_title(title: str):
    return re.match(r"^\[([A-Z_]+)\]", title).group(1)


def get_lab_number_from_title(title: str):
    return int(re.search(r"(\d)$", title).group(1))


def parse_ghdatestr_to_datestr(ghdatestr: str):
    return datetime.fromisoformat(ghdatestr[:-1]).strftime("%d.%m.%Y")


def parse_datestr_to_datetime(datestr: str):
    return datetime.strptime(datestr, "%d.%m.%Y")


def get_dates(created_at: str, closed_at: str):
    return (
        parse_ghdatestr_to_datestr(created_at),
        parse_ghdatestr_to_datestr(closed_at) if closed_at else "X"
    )


def get_data_from_pr(pr: dict):
    number = pr["number"]
    title = pr["title"].strip()
    return (number, None) if not is_valid_title(title, number) else (
        number,
        {"github": pr["user"]["login"],
         "title": title,
         "lab_number": get_lab_number_from_title(title),
         "lab_status": get_status_from_title(title),
         "dates": get_dates(pr["created_at"], pr["closed_at"])
         }
    )


def merge_dates(dates: list):
    # returns (earlier, later)
    # for starts date cannot be "X", so we're need first value -- earlier
    # for finish date we want latest date -- second value,
    #   so if a sate is "X" -- put it to the first place
    def compare_dates_str(first: str, second: str):
        if first == "X":
            return first, second
        elif second == "X":
            return second, first
        else:
            first_date = parse_datestr_to_datetime(first)
            second_date = parse_datestr_to_datetime(second)
            if  first_date <= second_date:
                return first, second
            else:
                return second, first

    earliest, latest = dates[0]
    for start, finish in dates:
        earliest = compare_dates_str(earliest, start)[0]
        latest = compare_dates_str(latest, finish)[1]
    return earliest[:5], latest[:5]  # omit year


def table_to_csv(table: list, fname: str):
    with open(fname + ".csv", 'w', newline='') as file:
        writer = csv.writer(file)
        for row in table:
            writer.writerow(row)


def make_header(labs_count: int):
    header = ["ФИО", "GitHub"]
    for num in range(1, labs_count + 1):
        header.append(f"lab{num}")
    return header


def make_table(header: list, students_names: dict, students_labs: defaultdict):
    table = [header]
    for github, labs in students_labs.items():
        row = [students_names[github], github]
        for num in range(1, 8):
            if num not in labs:
                continue
            start, finish = merge_dates(labs[num])  # [0] to tuple
            row.append(f"{start[:5]} -- {finish[:5]}")
        table.append(row)
    return table


def process_pull_requests(prs_json: list):
    students_labs = defaultdict(lambda: defaultdict(list))
    for pr in prs_json:
        number, data = get_data_from_pr(pr)
        if data:
            students_labs[data["github"]][data["lab_number"]].append(data["dates"])
    return students_labs


def process_repository(repo_info: dict):
    repo_name = repo_info["name"]
    repo_students = repo_info["students"]
    repo_labs_count = repo_info["labs_count"]
    print(f"[ II ] Process {repo_name} repository")
    pull_requests_list = load_json(json_fname(repo_name))
    students_labs = process_pull_requests(pull_requests_list)
    table = make_table(make_header(repo_labs_count), repo_students, students_labs)
    table_to_csv(table, repo_name)


def build_repo_prefix(university: str, course_title: str, year: int) -> str:
    return f"{university}_{course_title}_{str(year)}_"


def build_repo_info(course_prefix: str, group: dict) -> dict:
    return {"name": course_prefix + group["id"], "students": group["students"]}


def build_course_repositories(course: dict) -> list:
    repos_names_prefix = build_repo_prefix(
        course["university"], course["title"], course["year"])
    course_repositories = []
    for group in course["groups"]:
        repo_info = build_repo_info(repos_names_prefix, group)
        repo_info["labs_count"] = course["labs_count"]
        course_repositories.append(repo_info)
    return course_repositories


def build_repositories_to_process(courses: list) -> list:
    repositories = []
    for course in courses:
        repositories.extend(build_course_repositories(course))
    return repositories


def main():
    config = load_json(json_fname(__file__[:-3]))  # omit .py postfix
    github_account = config["github"]["account"]
    github_token = config["github"]["token"]
    user = github_account if github_account else input("GitHub user: ")
    token = github_token if github_token else input("GitHub access token: ")
    repositories = build_repositories_to_process(config["courses"])

    for repo in repositories:
        repo_name = repo["name"]
        # check cache
        if not os.path.isfile(json_fname(repo_name)) or \
                input(f"Cache for '{repo_name}' is exists. Reload? [N/y]: ") == "y":
            fetch_pull_requests(user, token, repo_name)
        process_repository(repo)
    print("[ II ] Success!")


if __name__ == "__main__":
    sys.exit(main())
