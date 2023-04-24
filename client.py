from commands import *
import grpc
import new_route_guide_pb2 as proto
import new_route_guide_pb2_grpc
import atexit

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
            current_leader_server, current_leader_port = self.replica_addresses[0]
            try:
                self.connection = new_route_guide_pb2_grpc.CalendarStub(grpc.insecure_channel(f"{current_leader_server}:{current_leader_port}"))
                response = self.connection.alive_ping(proto.Text(text=IS_ALIVE))
                if response.text == LEADER_ALIVE:
                    # Send message notifying new server that they're the leader
                    confirmation = self.connection.notify_leader(proto.Text(text=LEADER_NOTIFICATION))
                    if confirmation.text == LEADER_CONFIRMATION:
                        print("SWITCHING REPLICAS")
                        return
                
                # If for some reason, it gets here (failure), remove current leader from list of ports
                self.replica_addresses.pop(0)
            except Exception as e:
                # TODO REMOVE PRINT LATER
                print(e)
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
        print("Press 0 to schedule a new event.")
        print("Press 1 to see all current events.")
        print("Press 2 to search for events.")
        print("Press 3 to edit an event.")
        print("Press 4 to delete an event.")
        print("Press 5 to see all users.")
        print("Press 6 to logout.")
        print("Press 7 to delete your account.")

        action = input("What would you like to do?\n")
        if action == "0":
            self.schedule_event()
        elif action == "1":
            self.display_events()
        elif action == "2":
            self.search_events()
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
            elif action == "1":
                username, logged_in = self.enter_user(action)
                self.logged_in = logged_in
    
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
                elif purpose == "1":
                    response = self.connection.login_user(new_text)
                
                print(response.text)
                done = True

                if response.text == LOGIN_SUCCESSFUL:
                    self.logged_in = True
                    self.username = username
                    return username, True

            except Exception as e:
                # Power transfer to a backup replica
                self.find_next_leader()

        return username, False

    '''Displays username accounts for the user to preview given prompt.'''
    def display_accounts(self):
        recipient = input("What users would you like to see? Use a regular expression. Enter nothing to skip.\n")
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
    

    '''Notifies a new event for the user.'''
    def notify_new_event(self):
        print("NOT IMPLEMENTED")

    
    '''Schedules a new event for the user.'''
    def schedule_event(self):
        print("NOT IMPLEMENTED")
    

    '''Displays all events for the user.'''
    def display_events(self):
        print("NOT IMPLEMENTED")


    '''Searches for events for the user.'''
    def search_events(self):
        print("NOT IMPLEMENTED")


    '''Edits an event for the user.'''
    def edit_event(self):
        print("NOT IMPLEMENTED")
    

    '''Deletes an event for the user.'''
    def delete_event(self):
        print("NOT IMPLEMENTED")




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