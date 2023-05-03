# CS262 Final Project: Calendar Application

Engineering Ledger/Final Report: https://docs.google.com/document/d/1bzkWaMzJvpgZMV6NxDX6pcs4tWTEWMRZHzOwWnqHnxE/edit?usp=sharing
Presentation Slides: https://docs.google.com/presentation/d/188GuuyO3muI8_BGDIgOTj-N4kVY2nPEw60CfmA4uHa4/edit?usp=sharing

## Running the Code

### Setup
1. Setup a new environment through `spec-file.txt`. Run `conda create --name <env> --file spec-file.txt`
2. Run `conda activate <env>`.
3. Change the server address `SERVER1`, `SERVER2`, `SERVER3` values in `commands.py` to the `hostname` of your servers. To find hostname, enter `hostname` on your terminal.

### Running the Servers
1. Open a new terminal session for each server.
2. Run `python3 run_calendar_server{n}.py` such that `{n}` is the server number. For example, for server 1, run `python3 run_calendar_server1.py`.

### Running the Clients
1. Open a new terminal session for each client.
2. Run `python3 run_calendar_client.py`.
3. Follow the prompts provided to schedule, edit, and delete calendar events. You can initialize as many client sessions as you'd like on different machines.

### Persistence Server
In the situation that all three servers are down, a new set of servers can be brought up with the last state, including any unsent messages.
1. First rerun two servers by executing `python3 run_calendar_server2.py` and `python3 run_calendar_server3.py` on separate servers.
2. To customize the log file you reference for the latest state, change the `logname` variable. Note, `logname` cannot be named `1.log`, `2.log`, or `3.log` since the server cannot reference a log that it's trying to write to at the same time.
3. Open a new terminal session for the primary server.
4. Run `python3 run_chat_server_persistence.py`.
5. All three servers will then be synced and have the same state as the reference logs.

## Understanding Log Files
- Each log file is named according to the assigned server writing to that file (either `1.log`, `2.log`, or `3.log`).
- Log files capture all major actions of the chat messaging service.
- Log files can be used to provide persistence of the system.

## Running Tests
1. To run server tests, run `pytest server_tests.py`
2. To run process tests, run `pytest process_tests.py`