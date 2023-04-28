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
    def __init__(self, id=0, address=None, logfile = None):
        self.ip, self.port = address
        self.id = id

        self.accounts = [] # Usernames of all accounts
        self.active_accounts = [] # Username of all accounts that are currently logged in
        self.new_event_notifications = {} # {username: [event1, event2, event3]}
        self.events = [] # [event1, event2, event3]

        self.is_leader = False
        self.backup_connections = {} # len 1 if a backup, len 2 if leader (at start)
        self.other_servers = {} # for logging purposes
        self.next_event_id = 1

        # Sets up logging functionality
        for replica_id, address in REPLICA_IDS:
            self.setup_logger(f'{replica_id}', f'{replica_id}.log')
        
        if logfile:
            # Persistence: all servers went down and set up this server from the log file
            self.set_state_from_file(logfile)

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
    # TODO: CHANGE THIS!!
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

        # elif purpose == UPDATE_SUCCESSFUL:
        #     username = parsed_line[1]
        #     request = proto.Text()
        #     request.text = username

        #     self.replica_client_receive_message(request, None)

        #     self.delete_account(request, None)
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
    def connect_to_replicas(self):
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
        
        print("Connected to replicas")

    '''Determines whether server being pinged is alive and can respond.'''
    def alive_ping(self, request, context):
        return proto.Text(text=LEADER_ALIVE)

    """Notify the server that they are the new leader."""
    def notify_leader(self, request, context):
        self.sync_backups()
        print("Backup syncing is done")
        self.is_leader = True
        return proto.Text(text=LEADER_CONFIRMATION)

    """Syncs the backups with the new leader's state."""
    def sync_backups(self):
        # Operates on the assumption that the new leader is the first (of all the backups) to sync with ex-leader
        # Send all accounts to backups
        new_leader_log_file = f'{self.id}.log'
        for replica in self.backup_connections:
            replica_log_file = f'{self.backup_connections[replica]}.log'
            
            lines1 = list(open(new_leader_log_file, "r"))
            lines2 = list(open(replica_log_file, "r"))

            if len(lines1) != len(lines2):
                # Not synced; lines1 must have more lines
                for unsynced_line in lines1[len(lines2):]:
                    self.process_line(unsynced_line)

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

            # If leader, sync replicas
            if self.is_leader:
                new_text = proto.Text()
                new_text.text = username
                print("back up connections: ", self.backup_connections)
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
                print(e)
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

            # Delete all events created by this user
            for event in self.events:
                if event.host == username:
                    self.delete_event(event)

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
    

    def convert_event_to_proto(self, event):
        formatted_message = proto.Event()
        formatted_message.id = event.id
        formatted_message.host = event.host
        formatted_message.starttime = event.starttime
        formatted_message.duration = event.duration
        formatted_message.description = event.description
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
    

    '''Schedules a new event for the user.'''
    def schedule_event(self, request, context):
        host = request.host
        starttime = request.starttime
        duration = request.duration
        description = request.description

        new_event = Event(id=self.next_event_id, host=host, starttime=starttime, duration=duration, description=description)
        new_starttime = datetime.datetime.utcfromtimestamp(new_event.starttime)
        new_event_endtime = new_starttime + datetime.timedelta(hours=new_event.duration)
        mutex_events.acquire()
        for event in self.events:
            event_starttime = datetime.datetime.utcfromtimestamp(event.starttime)
            event_endtime = event_starttime + datetime.timedelta(hours=event.duration)
            if not (new_event_endtime <= event_starttime or event_endtime <= new_starttime):
                # TODO: CHECK THIS LATER
                mutex_events.release()
                return proto.Text(text=EVENT_CONFLICT)
        self.events.append(new_event)
        self.next_event_id += 1
        mutex_events.release()

        # Update notifications for all accounts
        for user in self.accounts:
            if user != host:
                mutex_new_event_notifications.acquire()
                self.new_event_notifications[user].append(new_event)
                mutex_new_event_notifications.release()

        return proto.Text(text=EVENT_SCHEDULED)


    '''Searches for events for the user.'''
    def search_events(self, request, context):
        print("here!!!")
        function = request.function
        value = request.value

        if function==SEARCH_ALL_EVENTS:
            # TODO: order self.events
            if len(self.events) == 0:
                return proto.Event(description = "No events to display.")
            for event in self.events:
                yield self.convert_event_to_proto(event)
        elif function==SEARCH_USER:
            none_found = True
            for event in self.events:
                x = re.search(value, event.host)
                if x is not None:
                    none_found=False
                    yield self.convert_event_to_proto(event)
            if none_found:
                yield proto.Event(description=NO_USER)
        elif function==SEARCH_TIME:
            print("NOT IMPLEMENTED")
        elif function==SEARCH_DESCRIPTION:
            none_found = True
            for event in self.events:
                x = re.search(value, event.description)
                if x is not None:
                    none_found=False
                    yield self.convert_event_to_proto(event)
            if none_found:
                yield proto.Event(description = "No description matches this!")


    '''Edits an event for the user.'''
    def edit_event(self, request, context):
        # TODO: check for conflicts later
        event_id = request.id
        for event in self.events:
            if event.id == event_id:
                mutex_events.acquire()
                event.starttime = request.starttime
                event.duration = request.duration
                event.description = request.description
                mutex_events.release()
                return proto.Text(text=UPDATE_SUCCESSFUL)
        
        return proto.Text(text=ACTION_UNSUCCESSFUL)
    

    '''Deletes an event for the user.'''
    def delete_event(self, request, context):
        event_id = request.id
        for event in self.events:
            if event.id == event_id:
                mutex_events.acquire()
                self.events.remove(event)
                mutex_events.release()
                return proto.Text(text=EVENT_DELETED)
        
        return proto.Text(text=ACTION_UNSUCCESSFUL)
    

"""Class for running server backend functionality."""
class ServerRunner:
    """Initialize a server instance."""
    def __init__(self, id = 0, address = (None, None), logfile=None):
        self.id = id
        self.ip, self.port = address

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self.calendar_servicer = CalendarServicer(id=self.id, address=address, logfile=logfile)
    
    """Function for starting server."""
    def start(self):
        proto_grpc.add_CalendarServicer_to_server(self.calendar_servicer, self.server)
        self.server.add_insecure_port(f"[::]:{self.port}")
        self.server.start()

    """Function for waiting for server termination."""
    def wait_for_termination(self):
        self.server.wait_for_termination()
    
    """Function for connecting to replicas."""
    def connect_to_replicas(self):
        self.calendar_servicer.connect_to_replicas()

    """Function for stopping server."""
    def stop(self):
        self.server.stop(grace=None)
        self.thread_pool.shutdown(wait=False)



"""
'''Handles the clients receiving messages sent to them. Delivers the message to the clients then clears sent messages'''
    def client_receive_message(self, request, context):
        lastindex = 0
        recipient = request.text

        # Write to logs
        text = UPDATE_SUCCESSFUL + SEPARATOR + recipient
        try:
            logger = logging.getLogger(f'{self.port}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(new_route_guide_pb2.Note(sender=f'{self.port}', recipient="", message=text))
        except Exception as e:
            print("Error logging update")

        mutex_unsent_messages.acquire()
        while len(self.unsent_messages[recipient]) > lastindex:
            sender, message = self.unsent_messages[recipient][lastindex]
            lastindex += 1
            formatted_message = new_route_guide_pb2.Note()
            formatted_message.recipient = recipient
            formatted_message.sender = sender
            formatted_message.message = message
            yield formatted_message
        mutex_unsent_messages.release()
        self.unsent_messages[recipient] = []

        # If leader, sync replicas
        if self.is_leader:
            print("Updating backups...")
            for connection in self.backup_connections:
                try:
                    response = connection.replica_client_receive_message(request)
                    if response.text != UPDATE_SUCCESSFUL:
                        print("error with update backup")
                except Exception as e:
                    print("Backup is down")

        return new_route_guide_pb2.Text(text=UPDATE_SUCCESSFUL)
    
    '''Replica handles the clients receiving messages sent to them. Updates the message states of the backups.'''
    def replica_client_receive_message(self, request, context):
        recipient = request.text
        mutex_unsent_messages.acquire()
        self.unsent_messages[recipient] = []
        mutex_unsent_messages.release()
        
        # Write to logs
        text = UPDATE_SUCCESSFUL + SEPARATOR + recipient
        try:
            logger = logging.getLogger(f'{self.port}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(new_route_guide_pb2.Note(sender=f'{self.port}', recipient="", message=text))
        except Exception as e:
            print("Error logging to other servers")
        
        return new_route_guide_pb2.Text(text=UPDATE_SUCCESSFUL)

    '''Handles the clients sending messages to other clients'''
    def client_send_message(self, request, context):
        recipient = request.recipient
        sender = request.sender
        message = request.message
        mutex_unsent_messages.acquire()
        self.unsent_messages[recipient].append((sender, message))
        mutex_unsent_messages.release()

        # If leader, sync replicas
        if self.is_leader:
            new_message = new_route_guide_pb2.Note()
            new_message.sender = sender
            new_message.recipient = recipient
            new_message.message = message
            for replica in self.backup_connections:
                response = None
                # Block until backups have been successfully updated
                try:
                    response = replica.client_send_message(new_message)
                except Exception as e:
                    print("Backup is down")
        
        # Write to logs
        text = SEND_SUCCESSFUL + SEPARATOR + sender + SEPARATOR + recipient + SEPARATOR + message
        try:
            logger = logging.getLogger(f'{self.port}')
            logger.info(text)
            for other in self.other_servers:
                other.log_update(new_route_guide_pb2.Note(sender=f'{self.port}', recipient="", message=text))
        except Exception as e:
            print("Error logging to other servers")
        return new_route_guide_pb2.Text(text=SEND_SUCCESSFUL)"""