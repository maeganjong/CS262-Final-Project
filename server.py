import grpc
from grpc._server import _Server
import new_route_guide_pb2 as proto
import new_route_guide_pb2_grpc as proto_grpc

import socket 
import threading
from concurrent import futures
import re
from commands import *

import logging
import threading
import datetime

mutex_accounts = threading.Lock()
mutex_active_accounts = threading.Lock()
mutex_new_event_notifications = threading.Lock()
mutex_events = threading.Lock()

class CalendarServicer(proto_grpc.CalendarServicer):
    '''Initializes CalendarServicer that sets up the datastructures to store user accounts and messages.'''
    def __init__(self, id=0, address=(None, None)):
        self.ip, self.port = address
        self.id = id

        self.accounts = [] # Usernames of all accounts
        self.active_accounts = [] # Username of all accounts that are currently logged in
        self.new_event_notifications = {} # {username: [event1, event2, event3]}

        # three event-related databases that follow will be guarded by mutex_events (only one edit to all events at a time)
        self.public_events = [] # [event1, event2, event3]
        self.private_events = [] # [event1, event2, event3]
        # maps username to list of private events they are a part of or they are hosting
        self.private_mappings = {} # {username: [event_id1, event_id2, event_id3]}

        self.is_leader = False
        self.backup_connections = {} # len 1 if a backup, len 2 if leader (at start)
        self.other_servers = {} # for logging purposes
        self.next_event_id = 1

        # Sets up logging functionality
        for replica_id, address in REPLICA_IDS:
            self.setup_logger(f'{replica_id}', f'{replica_id}.log')
        

    '''Initializes the logging meta settings'''
    def setup_logger(self, logger_name, log_file, level=logging.INFO):
        l = logging.getLogger(logger_name)
        formatter = logging.Formatter('%(message)s')
        fileHandler = logging.FileHandler(log_file, mode='w')
        fileHandler.setFormatter(formatter)
        streamHandler = logging.StreamHandler()
        streamHandler.setFormatter(formatter)

        l.setLevel(level)
        l.addHandler(fileHandler)
        l.addHandler(streamHandler) 

    '''Server sends its log writes to other replicas so all machines have same set of log files'''
    def log_update(self, request, context):
        machine = request.function
        log_message = request.value
        logger = logging.getLogger(machine)
        logger.info(log_message)
        return proto.Text(text="Done")

        
    '''Processes log files for starting the persistence server'''
    def process_line(self, line):
        header = "INFO:root:"
        line = line[:-1] # remove newline char at end of string
        if line.startswith(header):
                line = line[len(header):]
        parsed_line = line.split(SEPARATOR)
        
        purpose = parsed_line[0]

        # Handles all actions and replicates in the new server
        if purpose == LOGIN_SUCCESSFUL:
            username = parsed_line[1]
            request = proto.Text()
            request.text = username

            self.login_user(request, None)
        elif purpose == REGISTRATION_SUCCESSFUL:
            username = parsed_line[1]
            request = proto.Text()
            request.text = username

            self.register_user(request, None)
        
        elif purpose == EVENT_EDITED:
            id = int(parsed_line[1])
            starttime = int(parsed_line[2])
            duration = int(parsed_line[3])
            description = parsed_line[4]

            request = proto.Event()
            request.id = id
            request.description = description
            request.starttime = starttime
            request.duration = duration

            self.edit_event(request, None)

        elif purpose == PUBLIC_EVENT_SCHEDULED:
            host = parsed_line[1]
            starttime = int(parsed_line[2])
            duration = int(parsed_line[3])
            description = parsed_line[4]

            request = proto.Event()
            request.host = host
            request.description = description
            request.starttime = starttime
            request.duration = duration

            self.schedule_public_event(request, None)
        
        elif purpose == PRIVATE_EVENT_SCHEDULED:
            host = parsed_line[1]
            starttime = int(parsed_line[2])
            duration = int(parsed_line[3])
            description = parsed_line[4]
            guestlist = parsed_line[5]

            request = proto.Event()
            request.host = host
            request.description = description
            request.starttime = starttime
            request.duration = duration
            request.guestlist = guestlist

            self.schedule_private_event(request, None)

        elif purpose == EVENT_DELETED:
            event_id = int(parsed_line[1])
            request = proto.Event()
            request.id = event_id

            self.delete_event(request, None)

        elif purpose == LOGOUT_SUCCESSFUL:
            username = parsed_line[1]
            request = proto.Text()
            request.text = username

            self.logout(request, None)
    
    '''Sets up a server from the log file'''
    def set_state_from_file(self, logfile):
        f = open(logfile, "r")
        for line in f:
            self.process_line(line)

        f.close()

    '''Connects each replica based on the hierarchy of backups'''
    def connect_to_replicas(self, logfile=None):
        if self.id == 1:
            self.is_leader = True
            print("I am the leader")
            connection1 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER2}:{PORT2}"))
            connection2 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER3}:{PORT3}"))
            self.backup_connections[connection1] = 2
            self.backup_connections[connection2] = 3
            self.other_servers[connection1] = 2
            self.other_servers[connection2] = 3

            
        elif self.id == 2:
            print("I am first backup")
            connection1 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER1}:{PORT1}"))
            connection3 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER3}:{PORT3}"))
            self.backup_connections[connection3] = 3
            self.other_servers[connection1] = 1
            self.other_servers[connection3] = 3
        else:
            print("I am second backup")
            connection1 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER1}:{PORT1}"))
            connection2 = proto_grpc.CalendarStub(grpc.insecure_channel(f"{SERVER2}:{PORT2}"))
            self.other_servers[connection1] = 1
            self.other_servers[connection2] = 2
        
        print("Replica communication channels established.")
        if logfile:
            # Persistence: all servers went down and set up this server from the log file
            self.set_state_from_file(logfile)

    '''Determines whether server being pinged is alive and can respond.'''
    def alive_ping(self, request, context):
        return proto.Text(text=LEADER_ALIVE)

    '''Notify the server that they are the new leader.'''
    def notify_leader(self, request, context):
        self.sync_backups()
        print("Backup syncing is done")
        self.is_leader = True
        return proto.Text(text=LEADER_CONFIRMATION)

    '''Syncs the backups with the new leader's state.'''
    def sync_backups(self):
        # Operates on the assumption that the new leader is the first (of all the backups) to sync with ex-leader
        # Send all accounts to backups
        new_leader_log_file = f'{self.id}.log'
        for replica in self.backup_connections:
            replica_log_file = f'{self.backup_connections[replica]}.log'
            
            lines1 = list(open(new_leader_log_file, "r"))
            lines2 = list(open(replica_log_file, "r"))

            if len(lines1) > len(lines2):
                # Not synced; lines1 must have more lines
                for unsynced_line in lines1[len(lines2):]:
                    try:
                        replica.process_line(unsynced_line)
                    except Exception as e:
                        print("Error syncing backups")

    '''Logins the user by checking the list of accounts stored in the server session.'''
    def login_user(self, request, context):
        print("Logging in user")
        username = request.text
        
        if username not in self.accounts:
            return proto.Text(text="Username does not exist.")
        elif username in self.active_accounts:
            return proto.Text(text="User is already logged in.")
        else:
            # Log in user
            mutex_active_accounts.acquire()
            self.active_accounts.append(username)
            mutex_active_accounts.release()
        
        # If leader, sync replicas
        if self.is_leader:
            new_text = proto.Text()
            new_text.text = username
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    response = replica.login_user(new_text)
                except Exception as e:
                    print("Backup is down")
        
        # Write to logs
        text = LOGIN_SUCCESSFUL + SEPARATOR + username
        try:
            logger = logging.getLogger(f'{self.id}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(proto.Search(function=f'{self.id}', value=text))
        except Exception as e:
            print("Error logging to other servers")
        
        return proto.Text(text=LOGIN_SUCCESSFUL)

    '''Registers user given the client's input and compares with existing account stores.'''
    def register_user(self, request, context):
        username = request.text
        # Additional check for log reading in persistence
        if SEPARATOR in username:
            return proto.Text(text="Username cannot contain the character: {SEPARATOR}")
        
        if ", " in username:
            return proto.Text(text="Username cannot contain the character: ', '")
        
        if username in self.accounts:
            return proto.Text(text="Username already exists.")
        else:
            print(f"Registering {username}")
            # Register and log in user
            mutex_active_accounts.acquire()
            self.active_accounts.append(username)
            mutex_active_accounts.release()

            mutex_accounts.acquire()
            self.accounts.append(username)
            mutex_accounts.release()

            mutex_new_event_notifications.acquire()
            self.new_event_notifications[username] = []
            mutex_new_event_notifications.release()

            mutex_events.acquire()
            self.private_mappings[username] = []
            mutex_events.release()

            # If leader, sync replicas
            if self.is_leader:
                new_text = proto.Text()
                new_text.text = username
                print("Backup Connections: ", self.backup_connections)
                for replica in self.backup_connections:
                    response = None
                    # Block until backups have been successfully updated
                    try:
                        response = replica.register_user(new_text)
                    except Exception as e:
                        print("Backup is down")
            
            # Write to logs
            text = REGISTRATION_SUCCESSFUL + SEPARATOR + username
            try:
                logger = logging.getLogger(f'{self.id}')
                logger.info(text)
                for other in self.other_servers:
                    print(f"{self.id}")
                    other.log_update(proto.Search(function=f'{self.id}', value=text))
            except Exception as e:
                print("Error logging update")

            return proto.Text(text=LOGIN_SUCCESSFUL)
        
    '''Determines whether the user is currently in the registered list of users.'''
    def check_user_exists(self, request, context):
        username = request.text
        if username in self.accounts:
            return proto.Text(text="User exists.")
        else:
            return proto.Text(text=USER_DOES_NOT_EXIST)
        

    '''Deletes the account for the client requesting the deletion'''
    def delete_account(self, request, context):
        username = request.text
        try: 
            mutex_active_accounts.acquire()
            self.active_accounts.remove(username)
            mutex_active_accounts.release()

            mutex_new_event_notifications.acquire()
            del self.new_event_notifications[username]
            mutex_new_event_notifications.release()

            mutex_events.acquire()
            # Delete all private events user is a part of
            del self.private_mappings[username]

            # Delete all public events created by this user
            for event in self.public_events:
                if event.host == username:
                    self.delete_event(event)
            
            # Delete all private events created by this user
            for event in self.private_events:
                if event.host == username:
                    self.delete_event(event)
                
                if username in event.guestlist.split(", "):
                    new_guestlist = event.guestlist.split(", ").remove(username)
                    event.guestlist = ", ".join(new_guestlist)

            mutex_events.release()

            mutex_accounts.acquire()
            self.accounts.remove(username)
            mutex_accounts.release()
        except:
            return proto.Text(text=ACTION_UNSUCCESSFUL)

        # If leader, sync replicas
        if self.is_leader:
            new_text = proto.Text()
            new_text.text = username
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    response = replica.delete_account(new_text)
                except Exception as e:
                    print("Backup is down")

        # Write to logs
        text = DELETION_SUCCESSFUL + SEPARATOR + username
        try:
            logger = logging.getLogger(f'{self.id}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(proto.Search(function=f'{self.id}', value=text))
        except Exception as e:
            print("Error logging to other servers")
        
        return proto.Text(text=DELETION_SUCCESSFUL)
    
    '''Displays the current registered accounts that match the regex expression given by the client'''
    def display_accounts(self, request, context):
        none_found = True
        username = request.text
        for account in self.accounts:
            x = re.search(username, account)
            if x is not None:
                none_found = False
                yield proto.Text(text = x.string)
        if none_found:
            yield proto.Text(text = "No user matches this!")

    '''Logs out the user. Assumes that the user is already logged in and is displayed as an active account'''
    def logout(self, request, context):
        username = request.text
        mutex_active_accounts.acquire()
        self.active_accounts.remove(username)
        mutex_active_accounts.release()

        # If leader, sync replicas
        if self.is_leader:
            new_text = proto.Text()
            new_text.text = username
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    response = replica.logout(new_text)
                except Exception as e:
                    print("Backup is down")
        
        # Write to logs
        text = LOGOUT_SUCCESSFUL + SEPARATOR + username
        try:
            logger = logging.getLogger(f'{self.id}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(proto.Search(function=f'{self.id}', value=text))
        except Exception as e:
            print("Error logging to other servers")

        return proto.Text(text=LOGOUT_SUCCESSFUL)
    
    '''Helper function to convert the data into a gRPC message'''
    def convert_event_to_proto(self, event):
        formatted_message = proto.Event()
        formatted_message.id = event.id
        formatted_message.host = event.host
        formatted_message.starttime = event.starttime
        formatted_message.duration = event.duration
        formatted_message.description = event.description
        formatted_message.guestlist = event.guestlist
        return formatted_message
    

    '''Notifies a new event for the user.'''
    def notify_new_event(self, request, context):
        username = request.text
        mutex_new_event_notifications.acquire()
        new_events = self.new_event_notifications[username]
        for new_event in new_events:
            yield self.convert_event_to_proto(new_event)
        self.new_event_notifications[username] = []
        mutex_new_event_notifications.release()
        return proto.Text(text=UPDATE_SUCCESSFUL)
    
    '''Helper function to return True if there's a conflict, False if not'''
    def check_conflict(self, event1, event2, private=False):
        event1_starttime = datetime.datetime.fromtimestamp(event1.starttime)
        event1_endtime = event1_starttime + datetime.timedelta(hours=event1.duration)
        event2_starttime = datetime.datetime.fromtimestamp(event2.starttime)
        event2_endtime = event2_starttime + datetime.timedelta(hours=event2.duration)

        return not (event1_endtime <= event2_starttime or event2_endtime <= event1_starttime)
    

    '''Schedules a new public event for the user.'''
    def schedule_public_event(self, request, context):
        host = request.host
        starttime = request.starttime
        duration = request.duration
        description = request.description
        new_event = Event(id=self.next_event_id, host=host, starttime=starttime, duration=duration, description=description, guestlist="All")
        mutex_events.acquire()
        
        # Check conflict with public events
        for event in self.public_events:
            if self.check_conflict(new_event, event):
                mutex_events.release()
                return proto.Text(text=EVENT_CONFLICT)
        
        # Check conflict with private events
        for event in self.private_events:
            if self.check_conflict(new_event, event):
                mutex_events.release()
                return proto.Text(text=EVENT_CONFLICT)

        self.public_events.append(new_event)
        self.next_event_id += 1
        mutex_events.release()

        # Update notifications for all accounts
        for user in self.accounts:
            if user != host:
                mutex_new_event_notifications.acquire()
                self.new_event_notifications[user].append(new_event)
                mutex_new_event_notifications.release()

        # If leader, sync replicas
        if self.is_leader:    
            print("Backup Connections: ", self.backup_connections)
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    response = replica.schedule_public_event(request)
                except Exception as e:
                    print("Backup is down")

        text = PUBLIC_EVENT_SCHEDULED + SEPARATOR + host + SEPARATOR + str(starttime) + SEPARATOR + str(duration) + SEPARATOR + description
        try:
            logger = logging.getLogger(f'{self.id}')
            logger.info(text)
            for other in self.other_servers:
                print(f"{self.id}")
                other.log_update(proto.Search(function=f'{self.id}', value=text))
        except Exception as e:
            print("Error logging update")

        return proto.Text(text=PUBLIC_EVENT_SCHEDULED)


    '''Schedules a new private event for the user.'''
    def schedule_private_event(self, request, context):
        host = request.host
        starttime = request.starttime
        duration = request.duration
        description = request.description
        guestlist = request.guestlist
        new_event = Event(id=self.next_event_id, host=host, starttime=starttime, duration=duration, description=description, guestlist=guestlist)
        mutex_events.acquire()
        
        try:
            # Check conflict with public events
            for event in self.public_events:
                if self.check_conflict(new_event, event):
                    mutex_events.release()
                    return proto.Text(text=EVENT_CONFLICT)
            
            # Check conflict with private events for each person on guestlist
            for guest in guestlist.split(", "):
                event_ids = self.private_mappings[guest]
                for event in self.private_events:
                    if event.id in event_ids and self.check_conflict(new_event, event):
                        mutex_events.release()
                        return proto.Text(text=EVENT_CONFLICT)

            self.private_events.append(new_event)
            for guest in guestlist.split(", "):
                self.private_mappings[guest].append(new_event.id)
            self.private_mappings[host].append(new_event.id)
            
            self.next_event_id += 1
            mutex_events.release()

            # Update notifications for all invited accounts
            for user in guestlist.split(", "):
                if user != host:
                    mutex_new_event_notifications.acquire()
                    self.new_event_notifications[user].append(new_event)
                    mutex_new_event_notifications.release()
            
        except Exception as e:
            print("Error scheduling private event")

        # If leader, sync replicas
        if self.is_leader:    
            print("Backup Connections: ", self.backup_connections)
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    replica.schedule_private_event(request)
                except Exception as e:
                    print("Backup is down")

        text = PRIVATE_EVENT_SCHEDULED + SEPARATOR + host + SEPARATOR + str(starttime) + SEPARATOR + str(duration) + SEPARATOR + description + SEPARATOR + guestlist
        try:
            logger = logging.getLogger(f'{self.id}')
            logger.info(text)
            for other in self.other_servers:
                print(f"{self.id}")
                other.log_update(proto.Search(function=f'{self.id}', value=text))
        except Exception as e:
            print("Error logging update")

        return proto.Text(text=PRIVATE_EVENT_SCHEDULED)
    

    '''Searches for events for the user.'''
    def search_events(self, request, context):
        function = request.function
        value = request.value

        all_events = self.public_events + self.private_events

        # Displays all events
        if function==SEARCH_ALL_EVENTS:
            if len(all_events) == 0:
                return proto.Event(returntext=NO_MATCH)
            for event in all_events:
                yield self.convert_event_to_proto(event)
        # Displays events for a particular user
        elif function==SEARCH_USER:
            none_found = True
            for event in all_events:
                x = re.search(value, event.host)
                if x is not None:
                    none_found=False
                    yield self.convert_event_to_proto(event)
            if none_found:
                yield proto.Event(returntext=NO_MATCH)
        # Displays events for a particular description
        elif function==SEARCH_DESCRIPTION:
            none_found = True
            for event in all_events:
                x = re.search(value, event.description)
                if x is not None:
                    none_found=False
                    yield self.convert_event_to_proto(event)
            if none_found:
                yield proto.Event(returntext=NO_MATCH)


    '''Edits an event for the user.'''
    def edit_event(self, request, context):
        event_id = request.id
        new_event = Event(id=event_id, host=request.host, starttime=request.starttime, duration=request.duration, description=request.description)
        
        # Check conflicts against all public events
        for event in self.public_events:
            if self.check_conflict(new_event, event) and event.id != event_id:
                return proto.Text(text=EVENT_CONFLICT)
        
        # Check conflicts against all private events
        guestlist = None
        for event in self.private_events:
            if event.id == event_id:
                guestlist = event.guestlist
                break
        
        if guestlist is not None:
            for guest in guestlist:
                if guest in self.private_mappings:
                    event_ids = self.private_mappings[guest]
                    for event in self.private_events:
                        if event.id in event_ids and self.check_conflict(new_event, event):
                            return proto.Text(text=EVENT_CONFLICT)
        
        for event in self.public_events:
            if event.id == event_id:
                mutex_events.acquire()
                event.starttime = request.starttime
                event.duration = request.duration
                event.description = request.description
                mutex_events.release()

                # If leader, sync replicas
                if self.is_leader:    
                    print("Backup Connections: ", self.backup_connections)
                    for replica in self.backup_connections:
                        response = None
                        # Block until backups have been successfully updated
                        try:
                            response = replica.edit_event(request)
                        except Exception as e:
                            print("Backup is down")

                text = EVENT_EDITED + SEPARATOR + str(event_id) + SEPARATOR + str(request.starttime) + SEPARATOR + str(request.duration) + SEPARATOR + request.description
                try:
                    logger = logging.getLogger(f'{self.id}')
                    logger.info(text)
                    for other in self.other_servers:
                        print(f"{self.id}")
                        other.log_update(proto.Search(function=f'{self.id}', value=text))
                except Exception as e:
                    print("Error logging update")

                # Update other servers and then log
                return proto.Text(text=UPDATE_SUCCESSFUL)
        
        for event in self.private_events:
            if event.id == event_id:
                mutex_events.acquire()
                event.starttime = request.starttime
                event.duration = request.duration
                event.description = request.description
                mutex_events.release()

                # If leader, sync replicas
                if self.is_leader:    
                    print("Backup Connections: ", self.backup_connections)
                    for replica in self.backup_connections:
                        response = None
                        # Block until backups have been successfully updated
                        try:
                            response = replica.edit_event(request)
                        except Exception as e:
                            print("Backup is down")

                text = EVENT_EDITED + SEPARATOR + str(event_id) + SEPARATOR + str(request.starttime) + SEPARATOR + str(request.duration) + SEPARATOR + request.description
                try:
                    logger = logging.getLogger(f'{self.id}')
                    logger.info(text)
                    for other in self.other_servers:
                        print(f"{self.id}")
                        other.log_update(proto.Search(function=f'{self.id}', value=text))
                except Exception as e:
                    print("Error logging update")

                # Update other servers and then log
                return proto.Text(text=UPDATE_SUCCESSFUL)
            
        return proto.Text(text=ACTION_UNSUCCESSFUL)
    

    '''Deletes an event for the user.'''
    def delete_event(self, request, context):
        event_id = request.id
        for event in self.public_events:
            if event.id == event_id:
                mutex_events.acquire()
                self.public_events.remove(event)
                mutex_events.release()

                # If leader, sync replicas
                if self.is_leader:    
                    print("Backup Connections: ", self.backup_connections)
                    for replica in self.backup_connections:
                        response = None
                        # Block until backups have been successfully updated
                        try:
                            response = replica.delete_event(request)
                        except Exception as e:
                            print("Backup is down")

                text = DELETE_EVENT + SEPARATOR + str(event_id)
                try:
                    logger = logging.getLogger(f'{self.id}')
                    logger.info(text)
                    for other in self.other_servers:
                        print(f"{self.id}")
                        other.log_update(proto.Search(function=f'{self.id}', value=text))
                except Exception as e:
                    print("Error logging update")

                return proto.Text(text=EVENT_DELETED)
    
        for event in self.private_events:
            if event.id == event_id:
                mutex_events.acquire()
                self.private_events.remove(event)

                for username in event.guestlist.split(","):
                    self.private_mappings[username].remove(event_id)
                self.private_mappings[event.host].remove(event_id)

                mutex_events.release()

                # If leader, sync replicas
                if self.is_leader:    
                    print("Backup Connections: ", self.backup_connections)
                    for replica in self.backup_connections:
                        # Block until backups have been successfully updated
                        try:
                            replica.delete_event(request)
                        except Exception as e:
                            print("Backup is down")

                text = DELETE_EVENT + SEPARATOR + str(event_id)
                try:
                    logger = logging.getLogger(f'{self.id}')
                    logger.info(text)
                    for other in self.other_servers:
                        print(f"{self.id}")
                        other.log_update(proto.Search(function=f'{self.id}', value=text))
                except Exception as e:
                    print("Error logging update")

                return proto.Text(text=EVENT_DELETED)
        
        return proto.Text(text=ACTION_UNSUCCESSFUL)
    

'''Class for running server backend functionality.'''
class ServerRunner:
    '''Initialize a server instance.'''
    def __init__(self, id = 0, address = (None, None)):
        self.id = id
        self.ip, self.port = address

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self.calendar_servicer = CalendarServicer(id=self.id, address=address)
    
    '''Function for starting server.'''
    def start(self):
        proto_grpc.add_CalendarServicer_to_server(self.calendar_servicer, self.server)
        self.server.add_insecure_port(f"[::]:{self.port}")
        self.server.start()

    '''Function for waiting for server termination.'''
    def wait_for_termination(self):
        self.server.wait_for_termination()
    
    '''Function for connecting to replicas.'''
    def connect_to_replicas(self, logfile=None):
        self.calendar_servicer.connect_to_replicas(logfile=logfile)

    '''Function for stopping server.'''
    def stop(self):
        self.server.stop(grace=None)
        self.thread_pool.shutdown(wait=False)
