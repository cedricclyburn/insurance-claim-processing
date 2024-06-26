import os
import requests
import json

def test_security(endpoint, expected_serving_sha):
    response = requests.get(endpoint)

    if response.status_code==200:
        response_json = response.json()
    else:
        raise Exception(f"Response status code is {response.status_code}")

    if response_json["sha"] != expected_serving_sha:
        raise Exception(f"Serving SHA has changed, endpoint may have been tampered with")

    print(f"Security check OK")

    with open("security_result.json", "w") as f:
        json.dump({
            "serving_sha_match": response_json["sha"] == expected_serving_sha
        }, f)

if __name__ == '__main__':
    info_endpoint = "http://llm.ic-shared-llm.svc.cluster.local:3000" + "/info"
    expected_serving_sha = "630800eed37b15c4b0c9eb8e6ab47212026720f7"
    test_security(info_endpoint, expected_serving_sha)