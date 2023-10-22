import yaml
import sys
import time
import requests
import concurrent.futures
from threading import Thread
from urllib.parse import urlparse
from typing import List
from requests import RequestException
from concurrent.futures import ThreadPoolExecutor


domain_status_map = {}
HEALTHCHECK_INTERVAL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 0.5
MAX_THREADS = 200


class EndPointRecord:
    def __init__(self, yaml_dict: dict):
        self.name = yaml_dict["name"]
        self.url = yaml_dict["url"]
        self.domain = urlparse(self.url).netloc
        self.method = yaml_dict["method"] if "method" in yaml_dict else "GET"
        self.headers = yaml_dict["headers"] if "headers" in yaml_dict else None
        self.body = yaml_dict["body"] if "body" in yaml_dict else None

    def __str__(self):
        return f'Endpoint Name: {self.name}, Endpoint Domain: {self.domain}, URL: {self.url}, ' \
               f'HTTP Method: {self.method}, Headers: {self.headers}, Body: {self.body}'


class DomainRecord:
    def __init__(self, domain: str):
        self.domain = domain
        self.num_up = 0
        self.num_total = 0

    def add_down_result(self):
        self.num_total += 1

    def add_up_result(self):
        self.num_up += 1
        self.num_total += 1

    def get_availability(self) -> int:
        if self.num_total == 0:  # prevent division by zero
            return 0
        else:
            return round(100 * (self.num_up / self.num_total))


def parse_endpoints(file_name: str) -> List[EndPointRecord]:
    with open(file_name, "r") as stream:
        loaded = yaml.safe_load(stream)
        parsed_endpoints = []
        for endpoint in loaded:
            new_record = EndPointRecord(endpoint)
            domain_status_map[new_record.domain] = DomainRecord(new_record.domain)
            parsed_endpoints.append(new_record)
        return parsed_endpoints


def record_endpoint_status(response: requests.models.Response, domain: str):
    if not response:
        domain_status_map[domain].add_down_result()
    else:
        response_status = response.status_code
        if 200 < response_status or response_status > 299:
            domain_status_map[domain].add_down_result()
        else:
            domain_status_map[domain].add_up_result()


def check_endpoint_status(endpoint: EndPointRecord):
    response = None
    url = endpoint.url
    headers = endpoint.headers
    data = endpoint.body
    method = endpoint.method
    try:
        response = requests.request(method=method, url=url, headers=headers, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
    except RequestException:
        pass
    record_endpoint_status(response, endpoint.domain)


def start_threads(parsed_endpoints: List[EndPointRecord]):
    threads = []
    for endpoint in parsed_endpoints:
        t = Thread(target=check_endpoint_status, args=(endpoint,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


def display_availability():
    for record in domain_status_map.values():
        print(f'{record.domain} has {record.get_availability()}% availability percentage')
    print("---------------------------")


def main(argv):
    if len(argv) < 1:
        print("Invalid Arguments: Please provide one input YAML file")
    elif len(argv) > 1:
        print("Invalid Arguments: Please provide only one input YAML file")
    else:
        try:
            parsed_endpoints = parse_endpoints(argv[0])
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                while True:
                    futures = []
                    for endpoint in parsed_endpoints:
                        future = executor.submit(check_endpoint_status, endpoint)
                        futures.append(future)
                    for _ in concurrent.futures.as_completed(futures):
                        pass
                    display_availability()
                    time.sleep(HEALTHCHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("Ctrl-C Pressed, Stopping Program...")
        except yaml.YAMLError:
            print("Invalid YAML Format: Please reformat the input file")
        except FileNotFoundError:
            print("Invalid Arguments: Input YAML file not found")
        except Exception as e:
            print(f"Exception Thrown: {str(e)}")


if __name__ == "__main__":
    main(sys.argv[1:])
