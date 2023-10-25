# Fetch_Take_Home_Exercise Site Availability Monitor

Monitor the availability of multiple websites concurrently and display their uptime statistics.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)

## Features

- Monitor multiple websites concurrently.
- Check availability at regular intervals (15 seconds).
- Display availability percentages for each domain.
- Handle user interruptions (e.g., via `Ctrl+C`).

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

1. Prepare your YAML input file with site details. (Refer to `sites.yaml` for the format.)

2. Run the script with:

    ```bash
    python health_check.py sites.yaml
    ```

3. Monitor the availability statistics printed to the console.

4. Press `Ctrl+C` to stop monitoring and exit the program.
