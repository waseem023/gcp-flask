'''
Goal of Flask Microservice:
1. Flask will take the repository_name such as angular, angular-cli, material-design, D3 from the body of the api sent from React app and 
   will utilize the GitHub API to fetch the created and closed issues. Additionally, it will also fetch the author_name and other 
   information for the created and closed issues.
2. It will use group_by to group the data (created and closed issues) by month and will return the grouped data to client (i.e. React app).
3. It will then use the data obtained from the GitHub API (i.e Repository information from GitHub) and pass it as a input request in the 
   POST body to LSTM microservice to predict and forecast the data.
4. The response obtained from LSTM microservice is also return back to client (i.e. React app).
'''
# Import all the required packages 
import os
from flask import Flask, jsonify, request, make_response, Response
from flask_cors import CORS
import json
import dateutil.relativedelta
from dateutil import *
from datetime import date
import pandas as pd
import requests

# Initilize flask app
app = Flask(__name__)
# Handles CORS (cross-origin resource sharing)
CORS(app)

# Add response headers to accept all types of  requests
def build_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods",
                         "PUT, GET, POST, DELETE, OPTIONS")
    return response

# Modify response headers when returning to the origin
def build_actual_response(response):
    response.headers.set("Access-Control-Allow-Origin", "*")
    response.headers.set("Access-Control-Allow-Methods",
                         "PUT, GET, POST, DELETE, OPTIONS")
    return response


def fetch_pull_requests(repo_name):
    """
    Helper to fetch pull requests for a given repository from GitHub.
    """
    token = os.environ.get(
        'GITHUB_TOKEN', 'GITHUB_TOKEN')
    headers = {"Authorization": f'token {token}'}
    GITHUB_URL = "https://api.github.com/"
    pulls_url = GITHUB_URL + f"repos/{repo_name}/pulls?state=all&per_page=100"
    
    response = requests.get(pulls_url, headers=headers)
    pulls = response.json()

    pulls_data = []
    for pr in pulls:
        if "created_at" in pr:
            pulls_data.append({
                "pull_number": pr["number"],
                "created_at": pr["created_at"][:10]
            })

    return pulls_data

def fetch_branches(repo_name):
    """
    Fetches the list of branches for the given GitHub repository.
    """
    token = os.environ.get(
        'GITHUB_TOKEN', 'GITHUB_TOKEN')
    GITHUB_URL = "https://api.github.com/"
    headers = {
        "Authorization": f"token {token}"
    }
    
    branches_url = GITHUB_URL + f"repos/{repo_name}/branches"
    per_page = 100  # maximum
    params = {
        "per_page": per_page
    }

    branches_response = requests.get(branches_url, headers=headers, params=params)

    if branches_response.status_code != 200:
        print(f"Failed to fetch branches for {repo_name}: {branches_response.text}")
        return []
    
    branches_data = branches_response.json()

    branches_list = []
    today = date.today().isoformat()  # Today's date for all branches created_at placeholder

    for branch in branches_data:
        data = {}
        data["branch_name"] = branch["name"]
        data["created_at"] = today  # GitHub does not expose branch creation date via normal API
        branches_list.append(data)

    return branches_list

'''
API route github_tokenh is  "/api/forecast"
This API will accept only POST request
'''
@app.route('/api/github', methods=['POST'])
def github():
    body = request.get_json()
    # Extract the choosen repositories from the request
    repo_name = body['repository']
    print(repo_name + " repository")
    # Add your own GitHub Token to run it local
    token = os.environ.get(
        'GITHUB_TOKEN', 'GITHUB_TOKEN')
    GITHUB_URL = f"https://api.github.com/"
    headers = {
        "Authorization": f'token {token}'
    }
    params = {
        "state": "open"
    }
    repository_url = GITHUB_URL + "repos/" + repo_name
    # Fetch GitHub data from GitHub API
    repository = requests.get(repository_url, headers=headers)
    # Convert the data obtained from GitHub API to JSON format
    repository = repository.json()

    today = date.today()

    issues_reponse = []
    # Iterating to get issues for every month for the past 12 months
    for i in range(24):
        last_month = today + dateutil.relativedelta.relativedelta(months=-1)
        types = 'type:issue'
        repo = 'repo:' + repo_name
        ranges = 'created:' + str(last_month) + '..' + str(today)
        # By default GitHub API returns only 30 results per page
        # The maximum number of results per page is 100
        # For more info, visit https://docs.github.com/en/rest/reference/repos 
        per_page = 'per_page=100'
        # Search query will create a query to fetch data for a given repository in a given time range
        search_query = types + ' ' + repo + ' ' + ranges

        # Append the search query to the GitHub API URL 
        query_url = GITHUB_URL + "search/issues?q=" + search_query + "&" + per_page
        # requsets.get will fetch requested query_url from the GitHub API
        search_issues = requests.get(query_url, headers=headers, params=params)
        # Convert the data obtained from GitHub API to JSON format
        search_issues = search_issues.json()
        issues_items = []
        try:
            # Extract "items" from search issues
            issues_items = search_issues.get("items")
        except KeyError:
            error = {"error": "Data Not Available"}
            resp = Response(json.dumps(error), mimetype='application/json')
            resp.status_code = 500
            return resp
        if issues_items is None:
            continue
        for issue in issues_items:
            label_name = []
            data = {}
            current_issue = issue
            # Get issue number
            data['issue_number'] = current_issue["number"]
            # Get created date of issue
            data['created_at'] = current_issue["created_at"][0:10]
            if current_issue["closed_at"] == None:
                data['closed_at'] = current_issue["closed_at"]
            else:
                # Get closed date of issue
                data['closed_at'] = current_issue["closed_at"][0:10]
            for label in current_issue["labels"]:
                # Get label name of issue
                label_name.append(label["name"])
            data['labels'] = label_name
            # It gives state of issue like closed or open
            data['State'] = current_issue["state"]
            # Get Author of issue
            data['Author'] = current_issue["user"]["login"]
            issues_reponse.append(data)

        today = last_month
    df = pd.DataFrame(issues_reponse)
    # Daily Created Issues
   # Daily Created Issues: just count issue_number per created_at date
    df_created_at = (
            df
            .groupby('created_at', as_index=False)['issue_number']
        .count()
            .rename(columns={
            'created_at': 'date',
                'issue_number': 'count'
        })
        )
    '''
    Monthly Created Issues
    Format the data by grouping the data by month
    ''' 
    created_at = df['created_at']
    month_issue_created = pd.to_datetime(
        pd.Series(created_at), format='%Y-%m-%d')
    month_issue_created.index = month_issue_created.dt.to_period('m')
    month_issue_created = month_issue_created.groupby(level=0).size()
    month_issue_created = month_issue_created.reindex(pd.period_range(
        month_issue_created.index.min(), month_issue_created.index.max(), freq='m'), fill_value=0)
    month_issue_created_dict = month_issue_created.to_dict()
    created_at_issues = []
    for key in month_issue_created_dict.keys():
        array = [str(key), month_issue_created_dict[key]]
        created_at_issues.append(array)

    '''
    Monthly Closed Issues
    Format the data by grouping the data by month
    ''' 
    
    closed_at = df['closed_at'].sort_values(ascending=True)
    month_issue_closed = pd.to_datetime(
        pd.Series(closed_at), format='%Y-%m-%d')
    month_issue_closed.index = month_issue_closed.dt.to_period('m')
    month_issue_closed = month_issue_closed.groupby(level=0).size()
    month_issue_closed = month_issue_closed.reindex(pd.period_range(
        month_issue_closed.index.min(), month_issue_closed.index.max(), freq='m'), fill_value=0)
    month_issue_closed_dict = month_issue_closed.to_dict()
    closed_at_issues = []
    for key in month_issue_closed_dict.keys():
        array = [str(key), month_issue_closed_dict[key]]
        closed_at_issues.append(array)

    '''
        1. Hit LSTM Microservice by passing issues_response as body
        2. LSTM Microservice will give a list of string containing image github_tokenhs hosted on google cloud storage
        3. On recieving a valid response from LSTM Microservice, append the above json_response with the response from
            LSTM microservice
    '''
    created_at_body = {
        "issues": issues_reponse,
        "type": "created_at",
        "repo": repo_name.split("/")[1]
    }
    closed_at_body = {
        "issues": issues_reponse,
        "type": "closed_at",
        "repo": repo_name.split("/")[1]
    }

    pulls_data = fetch_pull_requests(repo_name)
    branches_data = fetch_branches(repo_name)

    LSTM_API_URL = "https://lstm-app-708210591622.us-central1.run.app/api/forecast"
    LSTM_API_URL_PULLS = "https://lstm-app-708210591622.us-central1.run.app/api/forecast/pulls"
    LSTM_API_URL_BRANCHES = "https://lstm-app-708210591622.us-central1.run.app/api/forecast/branches"

    created_at_response = requests.post(LSTM_API_URL,
                                        json=created_at_body,
                                        headers={'content-type': 'application/json'})

    closed_at_response = requests.post(LSTM_API_URL,
                                    json=closed_at_body,
                                    headers={'content-type': 'application/json'})

    if len(pulls_data) > 0:
        pulls_body = {
            "pulls": pulls_data,  # ✅ fixed here
            "repo": repo_name.split("/")[1]
        }
        pulls_response = requests.post(LSTM_API_URL_PULLS,
                                    json=pulls_body,
                                    headers={'content-type': 'application/json'})

        if pulls_response.status_code == 200:
            pulls_forecast_json = pulls_response.json()
        else:
            pulls_forecast_json = None
    else:
        pulls_forecast_json = None
    print("branches_data", branches_data)
    if branches_data:
        branches_body = { "branches": branches_data, "repo": repo_name.split("/")[1] }
        branches_response = requests.post(LSTM_API_URL_BRANCHES, json=branches_body, headers={'content-type': 'application/json'})
        
        if branches_response.status_code == 200:
            branches_forecast_json = branches_response.json()
            print("branches_response", branches_forecast_json)
        else:
            print(f"Failed to forecast branches for {repo_name}. HTTP Status: {branches_response.status_code}")
            branches_forecast_json = {
                "model_loss_image_url": None,
                "lstm_generated_image_url": None,
                "all_branches_data_image": None,
                "prophet_forecast_image_url": None,
                "sarimax_forecast_image_url": None
            }
    else:
        branches_forecast_json = None
    print("pulls_response", pulls_response.json())
    print("branches_response", branches_response.json())
    
    '''
    Create the final response that consists of:
        1. GitHub repository data obtained from GitHub API
        2. Google cloud image urls of created and closed issues obtained from LSTM microservice
    '''
    json_response = {
    "created": created_at_issues,
    "closed": closed_at_issues,
    "starCount": repository["stargazers_count"],
    "forkCount": repository["forks_count"],
    "createdAtImageUrls": {
        "model_loss_image_url": created_at_response.json().get("model_loss_image_url"),
        "lstm_generated_image_url": created_at_response.json().get("lstm_generated_image_url"),
        "all_issues_data_image": created_at_response.json().get("all_issues_data_image"),
        "prophet_forecast_image_url": created_at_response.json().get("prophet_forecast_image_url"),
        "sarimax_forecast_image_url": created_at_response.json().get("sarimax_forecast_image_url")  
    },
    "closedAtImageUrls": {
        "model_loss_image_url": closed_at_response.json().get("model_loss_image_url"),
        "lstm_generated_image_url": closed_at_response.json().get("lstm_generated_image_url"),
        "all_issues_data_image": closed_at_response.json().get("all_issues_data_image"),
        "prophet_forecast_image_url": closed_at_response.json().get("prophet_forecast_image_url"),
        "sarimax_forecast_image_url": closed_at_response.json().get("sarimax_forecast_image_url")   

     },
     "pullsForecastImageUrls": {   # <== CHANGED from "pullsAtImageUrls"
    "model_loss_image_url": pulls_forecast_json.get("model_loss_image_url") if pulls_forecast_json else None,
    "lstm_generated_image_url": pulls_forecast_json.get("lstm_generated_image_url") if pulls_forecast_json else None,
    "all_pulls_data_image": pulls_forecast_json.get("all_pulls_data_image") if pulls_forecast_json else None,
    "prophet_forecast_image_url": pulls_forecast_json.get("prophet_forecast_image_url") if pulls_forecast_json else None,
    "sarimax_forecast_image_url": pulls_forecast_json.get("sarimax_forecast_image_url") if pulls_forecast_json else None
    }   ,
    "branchesForecastImageUrls": {
            "model_loss_image_url": branches_forecast_json.get("model_loss_image_url") if branches_forecast_json else None,
            "lstm_generated_image_url": branches_forecast_json.get("lstm_generated_image_url") if branches_forecast_json else None,
            "all_branches_data_image": branches_forecast_json.get("all_branches_data_image") if branches_forecast_json else None,
            "prophet_forecast_image_url": branches_forecast_json.get("prophet_forecast_image_url") if branches_forecast_json else None,
            "sarimax_forecast_image_url": branches_forecast_json.get("sarimax_forecast_image_url") if branches_forecast_json else None
        }
    }
    # Return the response back to client (React app)
    return jsonify(json_response)

@app.route('/api/stars', methods=['GET'])
def github_stars_chart():
    # List of repositories to fetch from GitHub
    repositories = [
        "ollama/ollama",
        "langchain-ai/langchain",
        "langchain-ai/langgraph",
        "microsoft/autogen",
        "openai/openai-cookbook",
        "meta-llama/llama3",
        "elastic/elasticsearch",
        "milvus-io/pymilvus"
    ]

    
    token = os.environ.get(
        'GITHUB_TOKEN', 'GITHUB_TOKEN')
    headers = {"Authorization": f'token {token}'} if token else {}

    # GitHub API root
    GITHUB_URL = "https://api.github.com/repos/"

    # Prepare data list
    repos_data = []
    for repo in repositories:
        url = GITHUB_URL + repo
        response = requests.get(url, headers=headers)
        data = response.json()
        repos_data.append({
            "name": repo.split("/")[-1],  # short repo name
            "stars": data.get("stargazers_count", 0)
        })

    print(repos_data)

    # Call forecasting service to get bar chart
    STAR_FORECAST_API = "https://lstm-app-708210591622.us-central1.run.app/api/stars"
    star_chart_response = requests.post(STAR_FORECAST_API,
                                        json={"repos": repos_data},
                                        headers={'content-type': 'application/json'})

    # Return the bar chart image URL to frontend
    return jsonify({
        "star_bar_chart_url": star_chart_response.json().get("star_bar_chart_url")
    })
@app.route('/api/forks', methods=['GET'])
def github_forks_chart():
    repositories = [
        "ollama/ollama",
        "langchain-ai/langchain",
        "langchain-ai/langgraph",
        "microsoft/autogen",
        "openai/openai-cookbook",
        "meta-llama/llama3",
        "elastic/elasticsearch",
        "milvus-io/pymilvus"
    ]

    token = os.environ.get(
        'GITHUB_TOKEN', 'GITHUB_TOKEN')
    headers = {"Authorization": f'token {token}'} if token else {}

    GITHUB_URL = "https://api.github.com/repos/"

    repos_data = []
    for repo in repositories:
        url = GITHUB_URL + repo
        response = requests.get(url, headers=headers)
        data = response.json()
        repos_data.append({
            "name": repo.split("/")[-1],
            "forks": data.get("forks_count", 0)
        })

    # Call forecasting service
    FORK_FORECAST_API = "https://lstm-app-708210591622.us-central1.run.app/api/forks"
    fork_chart_response = requests.post(FORK_FORECAST_API,
                                        json={"repos": repos_data},
                                        headers={'content-type': 'application/json'})

    return jsonify({
        "forks_bar_chart_url": fork_chart_response.json().get("forks_bar_chart_url")
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8081)
