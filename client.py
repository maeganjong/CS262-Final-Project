from commands import *
import grpc
import new_route_guide_pb2 as proto
import new_route_guide_pb2_grpc
import atexit
import os
import datetime

class CalendarClient:   
    '''Instantiates the CalendarClient and runs the user experience of cycling through calendar functionalities.'''
    def __init__(self, test=False):
        if test:
            return 
        
        """
        List of ports of replicas in order of priority (for power transfer)
        List will decrease in size as servers go down; first port in list is the leader
        """
        self.replica_addresses = [(SERVER1, PORT1), (SERVER2, PORT2), (SERVER3, PORT3)]
        self.connection = None

        # Establish connection to first server
        self.find_next_leader()

        atexit.register(self.disconnect)

        self.logged_in = False
        self.username = None

        while not self.logged_in:
            self.login()

        # Receive new events from when they were offline
        self.notify_new_event()
        
        while self.logged_in:
            self.display_menu()
            self.notify_new_event()

    '''Finds the next leader when the existing leader was down'''
    def find_next_leader(self):
        while len(self.replica_addresses) > 0:
            print(self.replica_addresses)
            current_leader_server, current_leader_port = self.replica_addresses[0]
            try:
                self.connection = new_route_guide_pb2_grpc.CalendarStub(grpc.insecure_channel(f"{current_leader_server}:{current_leader_port}"))
                response = self.connection.alive_ping(proto.Text(text=IS_ALIVE))
                if response.text == LEADER_ALIVE:
                    # Send message notifying new server that they're the leader
                    confirmation = self.connection.notify_leader(proto.Text(text=LEADER_NOTIFICATION))
                    print(confirmation)
                    if confirmation.text == LEADER_CONFIRMATION:
                        print("SWITCHING REPLICAS")
                        return
                
                # If for some reason, it gets here (failure), remove current leader from list of ports
                self.replica_addresses.pop(0)
            except Exception as e:
                # TODO REMOVE PRINT LATER
                print("I AM HERE")
                # Remove current leader from list of ports
                self.replica_addresses.pop(0)
        
        print("Could not connect to any server (all replicas down).")
        exit()

    '''Disconnect logs out user when process is interrupted.'''
    def disconnect(self):
        print("Disconecting...")
        try:
            # Logs out the user gracefully
            response = self.connection.logout(proto.Text(text=self.username))
            print(response.text)
        except Exception as e:
            # Power transfer to a backup replica
            self.find_next_leader()

    """Displays menu for user to select what to do next."""
    def display_menu(self):
        # TODO: MAYBE CHANGE THIS UI IDK?
        print()
        print("Press 0 to schedule a new event.")
        print("Press 1 to see all current events.")
        print("Press 2 to search for events.")
        print("Press 3 to edit an event.")
        print("Press 4 to delete an event.")
        print("Press 5 to see all users.")
        print("Press 6 to logout.")
        print("Press 7 to delete your account.")
        print()

        action = input("What would you like to do?\n")
        if action == "0":
            self.schedule_event()
        elif action == "1":
            self.display_events()
        elif action == "2":
            print("Press 0 to search by user.")
            # print("Press 1 to search by start time.")
            print("Press 1 to search by description.")

            option = input("What would you like to do?\n")
            if option=="0":
                self.search_events(option=SEARCH_USER)
            elif option=="1":
            #     self.search_events(option=SEARCH_TIME)
            # elif option=="2":
                self.search_events(option=SEARCH_DESCRIPTION)
            else:
                print("Invalid input. Try again.")
        elif action == "3":
            self.edit_event()
        elif action == "4":
            self.delete_event()
        elif action == "5":
            self.display_accounts()
        elif action == "6":
            self.logout()
        elif action == "7":
            self.delete_account()
        else:
            print("Invalid input. Try again.")


    '''Logins user by prompting either to register or login to their account.'''
    def login(self):
        logged_in = False
        while not logged_in:
            action = input("Enter 0 to register. Enter 1 to login.\n")
            if action == "0":
                username, logged_in = self.enter_user(action)
                self.logged_in = logged_in
                self.username = username
            elif action == "1":
                username, logged_in = self.enter_user(action)
                self.logged_in = logged_in
                self.username = username
    
    '''Helper function to login for users to either register or login.'''
    def enter_user(self, purpose):
        # Prompts user for username
        username = input("What's your username?\n")

        new_text = proto.Text()
        new_text.text = username

        response = None
        done = False
        while not done:
            try: 
                if purpose == "0":
                    response = self.connection.register_user(new_text)
                    # TODO: DISPLAY ALL EVENTS
                elif purpose == "1":
                    response = self.connection.login_user(new_text)
                
                print(response.text)
                done = True

                if response.text == LOGIN_SUCCESSFUL:
                    self.logged_in = True
                    self.username = username
                    return username, True

            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()

        return username, False

    '''Displays username accounts for the user to preview given prompt.'''
    def display_accounts(self):
        recipient = input("What users would you like to see? Use a regular expression. Enter nothing to view all.\n")
        new_text = proto.Text()
        new_text.text = recipient
        print("\nUsers:")
        done = False
        while not done:
            try:
                accounts = self.connection.display_accounts(new_text)
                for account in accounts:
                    print(account.text)
                done = True
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()


    def logout(self):
        done = False
        while not done:
            try:
                response = self.connection.logout(proto.Text(text=self.username))
                print(response.text)
                done = True
                if response.text == LOGOUT_SUCCESSFUL:
                    self.logged_in = False
                    self.username = None
                    self.login()
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()
    

    def delete_account(self):
        done = False
        while not done:
            try:
                response = self.connection.delete_account(proto.Text(text=self.username))
                print(response.text)
                done = True
                if response.text == DELETION_SUCCESSFUL:
                    self.logged_in = False
                    self.username = None
                    self.login()
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()
    

    def print_event(self, event):
        print("--------------------------------------------------")
        print(f"[{event.id}] Event By {event.host}")
        print(f"Event Description: {event.description}")
        starttime = datetime.datetime.utcfromtimestamp(event.starttime)
        endtime = starttime + datetime.timedelta(hours=event.duration)
        print(f"Starts at: {starttime}")
        print(f"Ends at: {endtime}")
        print("--------------------------------------------------")


    '''Notifies a new event for the user.'''
    def notify_new_event(self):
        done = False
        while not done:
            try:
                notifications = self.connection.notify_new_event(proto.Text(text=self.username))
                for notification in notifications:
                    self.print_event(notification)
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()

    def prompt_date(self):
        os.system(f'cal')
        leapyear = False
        done = False
        while not done:
            year = input("What year would you like your event to start at? (1 to 9999)\n")
            try:
                year = int(year)
                if not(year >= 1 and year <= 9999):
                    raise ValueError
                
                if ((year % 400 == 0) and (year % 100 == 0)) or ((year % 4 ==0) and (year % 100 != 0)):
                    leapyear = True
        
                done = True
            except:
                print("Year not inputted correctly.")
        
        done = False
        while not done:
            month = input("What month would you like your event to start at? (1-12)\n")
            try:
                month = int(month)
                if not(month >= 1 and month <= 12):
                    raise ValueError
                done = True
            except:
                print("Month not inputted correctly.")
      
        os.system(f'cal {month} {year}') # TODO: SOME ERROR CATCHING?

        done = False
        while not done:
            day = input("What day would you like your event to start at?\n")
            try:
                day = int(day)
                if month in [1,3,5,7,8,10,12]:
                    if not(day >= 1 and day <= 31):
                        raise ValueError
                elif month in [4,6,9,11]:
                    if not(day >= 1 and day <= 30):
                        raise ValueError
                elif month == 2:
                    if leapyear:
                        if not(day >= 1 and day <= 29):
                            raise ValueError
                    else:
                        if not(day >= 1 and day <= 28):
                            raise ValueError
                done = True
            except:
                print("Date inputted incorrectly")

        done = False
        while not done:
            hour = input("What hour would you like your event to start at? (0-23)\n")
            try:
                hour = int(hour)
                if not(hour >= 0 and hour <= 23):
                    raise ValueError
                done = True
            except:
                print("Hour inputted incorrectly")
        
        return year, month, day, hour
    

    '''Schedules a new event for the user.'''
    def schedule_event(self):
        year, month, day, hour = self.prompt_date()
        done = False
        while not done:
            duration = input("How long would you like your event to last for? Please enter a number in hours.\n")
            try:
                duration = int(duration)
                done = True
            except:
                print("Duration inputted incorrectly")

        description = input("How would you like to describe your event?\n")

        # TODO FINISH THIS STUFF
        dt = datetime.datetime(int(year), int(month), int(day), int(hour))
        utc_timestamp = dt.timestamp()

        new_event = proto.Event(host=self.username, starttime=int(utc_timestamp), duration=int(duration), description=description)

        done = False
        while not done:
            try:
                response = self.connection.schedule_event(new_event)
                print(response.text)
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()
    

    '''Displays all events for the user.'''
    def display_events(self):
        self.search_events(display_all=True)
    

    '''Searches for events for the user.'''
    def search_events(self, display_all=False, option=None, user=None):
        # 0 = user, 1 = description
        done = False
        events = []
        if display_all:
            while not done:
                try:
                    events = self.connection.search_events(proto.Search(function=SEARCH_ALL_EVENTS,value=""))
                    done = True
                except Exception as e:
                    print(e)
                    print("JELFJKSFJLK?")
                    # Power transfer to a backup replica
                    self.find_next_leader()
            
        else:
            if option==DISPLAY_USER:
                while not done:
                    try:
                        events = self.connection.search_events(proto.Search(function=SEARCH_USER,value=user))
                        done = True
                    except Exception as e:
                        print(e)
                        # Power transfer to a backup replica
                        self.find_next_leader()
            
            if option==SEARCH_USER:
                value=input("What's the user you'd like to search by?\n")
                while not done:
                    try:
                        events = self.connection.search_events(proto.Search(function=SEARCH_USER,value=value))
                        done = True
                    except Exception as e:
                        print(e)
                        # Power transfer to a backup replica
                        self.find_next_leader()
            
            elif option==SEARCH_DESCRIPTION:
                value=input("What's the description you'd like to search by?\n")
                while not done:
                    try:
                        events = self.connection.search_events(proto.Search(function=SEARCH_DESCRIPTION,value=value))
                        done = True
                    except Exception as e:
                        print(e)
                        # Power transfer to a backup replica
                        self.find_next_leader()
        try:
            for event in events:
                if event.returntext==NO_MATCH:
                    print(NO_MATCH)
                    return
                self.print_event(event)
        except Exception as e:
            # TODO: i don't know why we need this but it makes this work??
            print("why are we here?")


    '''Edits an event for the user.'''
    def edit_event(self):
        print("These are the events you have permission to edit:")
        result = self.search_events(option=DISPLAY_USER, user=self.username)

        # There's no events for the user to edit
        if result == NO_USER:
            return
        
        done = False
        while not done:
            event_id = input("What event would you like to edit? Please enter the event id.\n")
            try:
                event_id = int(event_id)
                done = True
            except:
                print("Invalid event id.")
                return
        
        # Checking permissions
        done = False
        while not done:
            try:
                user_events = self.connection.search_events(proto.Search(function=SEARCH_USER,value=self.username))
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()
        
        event_to_edit = None
        for user_event in user_events:
            if user_event.id == event_id:
                event_to_edit = user_event
                break
        
        if not event_to_edit:
            print("You do not have permission to edit this event or this event does not exist.")
            return
        
        # TODO: check valid event id/permissions and display current event details
        done = False
        while not done:
            try:
                edit_fields = input("Please enter all fields you'd like to edit. Separate each field with a comma. \n    [s] for start time\n    [d] for duration\n    [t] for description\n")
                if edit_fields == "":
                    print("No fields to edit.")

                test = edit_fields.split(",")
                for event in test:
                    if event not in ['s', 'd', 't']:
                        raise ValueError
                done = True
            except:
                print("Not inputted correctly!")

        
        print("Current Event Details:")
        self.print_event(event_to_edit)

        edit_fields = edit_fields.split(",")
        updated_event = proto.Event(id=event_id)
        updated_event.starttime = event_to_edit.starttime
        updated_event.duration = event_to_edit.duration
        updated_event.description = event_to_edit.description
        for field in edit_fields:
            if field == "s":
                year, month, day, hour = self.prompt_date()
                dt = datetime.datetime(int(year), int(month), int(day), int(hour))
                utc_timestamp = dt.timestamp()
                updated_event.starttime = int(utc_timestamp)
            elif field == "d":
                duration = input("How long would you like your event to last for? Please enter a number in hours.\n")
                updated_event.duration = int(duration)
            elif field == "t":
                description = input("What would you like to describe your event?\n")
                updated_event.description = description

        done = False
        while not done:
            try:
                response = self.connection.edit_event(updated_event)
                print(response.text)
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()
    

    '''Deletes an event for the user.'''
    def delete_event(self):
        # Display all events that the user created
        print("These are the events you have permission to delete:")
        result = self.search_events(option=DISPLAY_USER, user=self.username)

        if result == NO_USER:
            return

        event_id = input("What event would you like to delete? Please enter the event id.\n")
        try:
            event_id = int(event_id)
        except:
            print("Invalid event id.")
            return
        
        # Checking permissions
        done = False
        while not done:
            try:
                user_events = self.connection.search_events(proto.Search(function=SEARCH_USER,value=self.username))
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()
        
        event_to_edit = None
        for user_event in user_events:
            if user_event.id == event_id:
                event_to_edit = user_event
                break
        
        if not event_to_edit:
            print("You do not have permission to delete this event.")
            return
        
        done = False
        while not done:
            try:
                response = self.connection.delete_event(proto.Event(id=event_id))
                print(response.text)
                done = True
            except Exception as e:
                print(e)
                # Power transfer to a backup replica
                self.find_next_leader()



""" DELETE THIS LATER USE FOR REFERENCE!
    '''Prompts user to specify recipient of their message and the message body. Creates the Note object encompassing the message then sends the message to the server.'''
    def send_chat_message(self):
        recipient = input("Who do you want to send a message to?\n")
        new_text = proto.Text()
        new_text.text = recipient
        done = False
        while not done:
            try:
                response = self.connection.check_user_exists(new_text)
                if response.text == USER_DOES_NOT_EXIST:
                    print(response.text)
                    return False
                done = True
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()
        
        message = input("What's your message?\n")
        new_message = proto.Note()
        new_message.sender = self.username
        new_message.recipient = recipient
        new_message.message = message

        done = False
        while not done:
            try:
                output = self.connection.client_send_message(new_message)
                print(output.text)
                done = True
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()
        
        return True

    '''Handles the print of all the messages sent to the user.'''
    def print_messages(self):
        for message in self.receive_messages():
            print(message)

    '''User pulls message sent to them from the server.'''
    def receive_messages(self):
        done = False
        while not done:
            try:
                notes = self.connection.client_receive_message(proto.Text(text=self.username))
                for note in notes:
                    yield f"[{note.sender} sent to {note.recipient}] {note.message}"
                done = True
            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()
"""