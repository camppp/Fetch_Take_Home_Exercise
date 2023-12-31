# Fetch_Take_Home_Exercise Site Availability Monitor

Monitor the availability of multiple domains concurrently and display their uptime statistics.

## Table of Contents

- [Features](#features)
- [Design Considerations](#design-considerations)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)

## Features

- Monitor multiple domains concurrently.
- Check availability at regular intervals (15 seconds).
- Display availability percentages for each domain.
- Handle user interruptions (e.g., via `Ctrl+C`).
- Additional YAML test data containing different number of endpoints
- (sites.yaml: the original sample input file, sites_dummy.yaml: contains 20 real domain endpoints, sites_large.yaml: contains 10K endpoints for 20 real domains)

## Design Considerations
1. The YAML file could contain a large number of endpoints.
   - Instead of sequentially sending health check requests, perform the health checks in parallel using multithreading.
2. Local network can be saturated by the ongoing health checks, and response latency might be affected.
   - Avoid sending health checks all at once, limit the number of conccurent requests, and batch the endpoint list.
4. Creating and destroying threads every 15 seconds introduces significant overhead.
   - Use a thread pool to allow the program to reuse threads.
5. Different domains might have different rate limiting mechanisms.
   - Shuffle and batch the endpoint list in order to spread out health check requests for the same domain.
6. It is possible that the capabilities of the local network does not allow all endpoints to be checked in the 15 seconds interval.
   - Record the total time spent in sending requests for each interval. If this time is larger than 15 seconds, display a message to the user and exit the program.

## Prerequisites

* python 3.10.11
* pyYAML 6.0.1
* requests 2.23.0
* urllib3 1.24.3

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/camppp/Fetch_Take_Home_Exercise.git
    ```

2. Navigate to the project directory:

    ```bash
    cd Fetch_Take_Home_Exercise
    ```

3. Install required Python libraries:

    ```bash
    pip install -r requirements.txt
    ```
   
## Usage

1. Prepare your YAML input file with endpoint details. (Refer to `sites.yaml` for the format.)

2. Run the script with:

    ```bash
    python health_check.py sites.yaml
    ```

3. Monitor the availability statistics printed to the console.

4. Press `Ctrl+C` to stop monitoring and exit the program.
