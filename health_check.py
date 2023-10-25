import yaml
import sys
import time
import requests
import random
import signal
import concurrent.futures
from threading import RLock, Event
from urllib.parse import urlparse
from typing import List
from requests import RequestException
from concurrent.futures import ThreadPoolExecutor

# Global variables
sigint_event = Event()  # Event for handling SIGINT (Ctrl+C)
domain_status_map = {}  # Map to hold status of domains
HEALTHCHECK_INTERVAL_SECONDS = 15  # How often the check should be repeated
REQUEST_TIMEOUT_SECONDS = 0.5  # Maximum time to wait for a response
MAX_THREADS = 200  # Maximum concurrent threads


class EndpointRecord:
    """ Represents a single endpoint from the YAML file """
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
    """
    Represents a domain and calculates its availability based on its endpoints' results.
    Because we can have many threads updating the same domain record, we need to lock the object
    to prevent race conditions. In previous versions, I used a global lock for the global domain
    status map. This creates a performance bottleneck when a large number of threads are waiting for
    the same lock. Therefore, in the latest version, I gave each domain record a separate lock.
    """
    def __init__(self, domain: str):
        self.domain = domain
        self.num_up = 0
        self.num_total = 0
        self.lock = RLock()  # We associate each domain with a separate lock

    def add_endpoint_result(self, is_up: bool):
        with self.lock:  # Use lock to prevent race conditions
            if is_up:
                self.num_up += 1
            self.num_total += 1

    def get_availability(self) -> int:
        if self.num_total == 0:  # Prevent division by zero
            return 0
        else:
            return round(100 * (self.num_up / self.num_total))


def parse_endpoints(file_name: str) -> List[EndpointRecord]:
    """ Parses the YAML file and returns a list of endpoint records

    Args:
        file_name: The file name of the YAML file containing endpoint configurations

    Returns:
        A list of EndpointRecord object parsed from the YAML file

    Raises:
        FileNotFoundError: If the file path provided by the user is invalid
        YAMLError: If the YAML file contains invalid format
    """
    with open(file_name, "r") as stream:
        loaded = yaml.safe_load(stream)
        parsed_endpoints = []
        for endpoint in loaded:
            new_record = EndpointRecord(endpoint)
            if new_record.domain not in domain_status_map:
                domain_status_map[new_record.domain] = DomainRecord(new_record.domain)
            parsed_endpoints.append(new_record)
        return parsed_endpoints


def batch_endpoints(endpoints: List[EndpointRecord]) -> List[List[EndpointRecord]]:
    """
    Shuffles and breaks the list of endpoints into smaller batches for concurrent processing
    Batching endpoints helps in two aspects:
    1. Mitigate the effects of rate limiting mechanisms of certain domains
    2. Reduce the pressure on the local network by limiting the number concurrent health check requests

    Here we shuffle the endpoints to reduce the possibility that same domains are queried in the same batch.

    Batch size is dependent on the max number of threads allowed and the number of total endpoints. It can
    be configured to fit different healthcheck endpoint list sizes. Moreover, if there is a strict requirement
    to prevent triggering any rate limiting, we can create more batches to spread out the placement of the
    endpoints belonging to the same domain, but this is out of the scope for this exercise.

    Args:
        endpoints: The list of EndpointRecord objects parsed from the input YAML

    Returns:
        A 2-dimensional list of batched EndpointRecord objects
    """
    random.shuffle(endpoints)
    batch_size = min(MAX_THREADS * 2, len(endpoints))
    return [endpoints[i:i + batch_size] for i in range(0, len(endpoints), batch_size)]


def check_and_record_endpoint_status(endpoint: EndpointRecord):
    """
    Checks the status of an endpoint and records the result

    If the program already received SIGINT from the console, the healthcheck is not performed
    If the request encounters an error, the exception is caught and a DOWN result is recorded for the domain

    Otherwise, check if the response latency is less than 500ms and if the response status code is in
    the range of 200 and 299, and record the result in the global domain status map correspondingly

    Args:
        endpoint: The endpoint to perform healthcheck on
    """
    if sigint_event.is_set():
        return
    response = None
    url = endpoint.url
    domain = endpoint.domain
    headers = endpoint.headers
    data = endpoint.body
    method = endpoint.method
    try:
        response = requests.request(method=method, url=url, headers=headers, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
    except RequestException:
        pass
    is_domain_up = response is not None and 200 <= response.status_code <= 299
    domain_status_map[domain].add_endpoint_result(is_domain_up)


def display_availability():
    """ Displays the formatted availability percentage of each domain to the console """
    print("----------------------------------------")
    for record in domain_status_map.values():
        print(f'{record.domain} has {record.get_availability()}% availability percentage')
    print("----------------------------------------")


def sigint_handler(signum, frame):
    """ Handler function for SIGINT (Ctrl+C) signal """
    sigint_event.set()


def main(argv):
    """
    This is the entry point for the healthcheck script. In order to guarantee the efficiency of health checks, I've
    adopted a multithreading strategy for sending healthcheck requests. In previous versions, this is implemented
    by creating a separate thread for each endpoint. However, due to the periodic nature of our task, creating and
    destroying large number of threads every 15 seconds can be very inefficient. Therefore, in the latest version,
    I used a threadpool to provide the ability to reuse threads.

    If the input command line argument is invalid, print a message and exit the program
    If any exception is raised during execution, catch the exception, print the error message and exit the program
    If SIGINT is received from the console, set the threading event object, which will prevent any new healthcheck
    requests from being sent. Then the threadpool will be shutdown and the program will exit

    Because the size of the endpoint list is arbitrary. It is possible that 15 seconds is not enough for the script
    to send health checks to all endpoints. In that case, we print a message and exit the program
    """
    #
    if len(argv) < 1:
        print("Invalid Arguments: Please provide one input YAML file")
    elif len(argv) > 1:
        print("Invalid Arguments: Please provide only one input YAML file")
    else:
        signal.signal(signal.SIGINT, sigint_handler)  # Register the SIGINT handler function
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            try:
                parsed_endpoints = parse_endpoints(argv[0])
                batched_endpoints = batch_endpoints(parsed_endpoints)
                while not sigint_event.is_set():  # While loop will stop once SIGINT is received
                    start_time = time.time()
                    for batch in batched_endpoints:
                        futures = []
                        for endpoint in batch:
                            future = executor.submit(check_and_record_endpoint_status, endpoint)
                            futures.append(future)
                        for _ in concurrent.futures.as_completed(futures):
                            if sigint_event.is_set():  # Terminate the loop early if SIGINT is received
                                break
                        if sigint_event.is_set():
                            break
                    display_availability()
                    cur_time = time.time()
                    remain_time = HEALTHCHECK_INTERVAL_SECONDS - (cur_time - start_time)
                    # We record the total time it took to send health checks to all endpoints
                    # if this time is larger than 15 seconds, we need to inform the user to
                    # adjust endpoint list size or concurrency parameters, and then exit the program
                    if remain_time <= 0:
                        print("Too Many Concurrent Requests: Please adjust concurrency parameters")
                        break
                    end_time = cur_time + remain_time  # calculate the remaining time in the 15s window
                    while time.time() < end_time and not sigint_event.is_set():
                        # Hang the script for the remaining time, and check for the SIGINT signal every 0.1s
                        time.sleep(0.1)
                executor.shutdown(wait=False)
                print("\nCtrl-C Pressed, Stopping Program...")
            except yaml.YAMLError:
                print("Invalid YAML Format: Please reformat the input file")
            except FileNotFoundError:
                print("Invalid Arguments: Input YAML file not found")
            except Exception as e:
                print(f"Exception Thrown: {str(e)}")


if __name__ == "__main__":
    main(sys.argv[1:])
