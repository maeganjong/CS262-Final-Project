from server import CalendarServicer
from commands import *
from unittest.mock import MagicMock
from unittest.mock import patch
import new_route_guide_pb2 as proto
from io import StringIO

# pytest server_tests.py

# Replication Tests
def test_persistence():
    # Testing persistence
    server = CalendarServicer()

    server.connect_to_replicas(logfile="test_persistence.log")

    assert len(server.accounts) == 4
    assert "alyssa" in server.accounts
    assert "dale" in server.accounts
    assert "aly1" in server.accounts
    assert "dale1" in server.accounts
    assert len(server.active_accounts) == 0
    assert len(server.public_events) == 1
    assert len(server.private_events) == 3


def test_backup_sync():
    # TODO: FIX THIS LATER!
    # Testing backup sync
    return 
    replica_id, address = REPLICA_IDS[0]
    server = CalendarServicer(id=replica_id, address=address)

    server.replica_client_receive_message = MagicMock()
    server.client_send_message = MagicMock()

    server.backup_connections = {"test_backup": 1051}

    # No hanging message logged
    new_server = CalendarServicer(logfile="1051.log")
    assert "alyssa" in new_server.unsent_messages
    assert len(new_server.unsent_messages["alyssa"]) == 0

    # Test backup sync
    server.sync_backups()

    server.client_send_message.assert_called_once()
    server.replica_client_receive_message.assert_called_once()


# Testing account-specific functions

def test_login_flow():
    # Testing login flow
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    # Test username does not exist
    assert len(server.accounts) == 0
    server.login_user(request, None)
    proto.Text.assert_called_with(text="Username does not exist.")

    # Test user already logged in
    server.accounts.append("dale")
    server.active_accounts.append("dale")

    server.login_user(request, None)
    proto.Text.assert_called_with(text="User is already logged in.")

    # Test successful login
    server.active_accounts = []
    assert len(server.accounts) == 1

    server.login_user(request, None)
    proto.Text.assert_called_with(text=LOGIN_SUCCESSFUL)


def test_registration_flow():
    # Testing registration flow
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    # Test username already exists
    server.accounts.append("dale")
    assert len(server.accounts) == 1

    server.register_user(request, None)
    proto.Text.assert_called_with(text="Username already exists.")

    # Test successful login
    server.accounts = []

    server.register_user(request, None)
    assert len(server.accounts) == 1
    assert server.accounts[0] == "dale"
    
    assert "dale" in server.active_accounts
    assert "dale" in server.new_event_notifications
    assert "dale" in server.private_mappings

    proto.Text.assert_called_with(text=LOGIN_SUCCESSFUL)


def test_check_user_exists_flow():
    # Testing registration flow
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    # Test username does not exist
    assert len(server.accounts) == 0
    server.check_user_exists(request, None)
    proto.Text.assert_called_with(text=USER_DOES_NOT_EXIST)

    # Test successful find
    server.accounts.append("dale")
    server.check_user_exists(request, None)
    proto.Text.assert_called_with(text="User exists.")


def test_delete_account_flow():
    # Testing delete account flow
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    # Test delete account
    server.accounts.append("dale")
    server.active_accounts.append("dale")
    server.new_event_notifications["dale"] = ["new event"]
    server.private_mappings["dale"] = ["event_id"]

    server.delete_account(request, None)

    assert len(server.accounts) == 0
    assert "dale" not in server.active_accounts
    assert "dale" not in server.new_event_notifications
    assert "dale" not in server.private_mappings

    proto.Text.assert_called_with(text=DELETION_SUCCESSFUL)


def test_logout_flow():
    # Testing logout flow
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    # Test account account
    server.accounts.append("dale")
    server.active_accounts.append("dale")
    server.new_event_notifications["dale"] = ["new event"]
    server.private_mappings["dale"] = ["event_id"]

    server.logout(request, None)

    assert "dale" in server.accounts
    assert "dale" in server.new_event_notifications
    assert "dale" in server.private_mappings
    assert "dale" not in server.active_accounts

    proto.Text.assert_called_with(text=LOGOUT_SUCCESSFUL)


# Testing event-specific functions

def test_notify_new_event():
    return
    # Testing notify new event
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    proto.Event=MagicMock()
    request = MagicMock()
    request.text = "dale"
    event1 = Event()
    event2 = Event()
    server.new_event_notifications["dale"] = [event1, event2]

    # Test notify new event
    server.notify_new_event(request, None)
    assert proto.Event.call_count == 2

    assert "dale" in server.new_event_notifications
    print(server.new_event_notifications["dale"])
    assert len(server.new_event_notifications["dale"]) == 0

    proto.Text.assert_called_with(text=UPDATE_SUCCESSFUL)

# def test_client_receive_message_flow():
#     # Testing client receive message flow
#     server = CalendarServicer()

#     # Setting up mocks
#     proto.Text=MagicMock()
#     request = MagicMock()
#     request.text = "dale"
#     server.unsent_messages["dale"] = [("alyssa", "hi dale 1"), ("alyssa", "hi dale 2")]

#     # Test client send message
#     server.replica_client_receive_message(request, None)

#     assert "dale" in server.unsent_messages
#     assert len(server.unsent_messages["dale"]) == 0

#     proto.Text.assert_called_with(text=UPDATE_SUCCESSFUL)


# def test_client_send_message_flow():
#     # Testing client send message flow
#     server = CalendarServicer()

#     # Setting up mocks
#     proto.Text=MagicMock()
#     request = MagicMock()
#     request.recipient = "dale"
#     request.sender = "alyssa"
#     request.message = "hi dale"
#     server.unsent_messages["dale"] = []

#     # Test client send message
#     server.client_send_message(request, None)

#     assert "dale" in server.unsent_messages
#     assert len(server.unsent_messages["dale"]) == 1
#     assert server.unsent_messages["dale"][0][0] == "alyssa"
#     assert server.unsent_messages["dale"][0][1] == "hi dale"

#     proto.Text.assert_called_with(text="Message sent!")