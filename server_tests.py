from server import CalendarServicer
from commands import *
from unittest.mock import MagicMock
from unittest.mock import patch
import new_route_guide_pb2 as proto
from io import StringIO

# pytest server_tests.py

# Replication Tests

"""Testing persistence"""
def test_persistence():
    server = CalendarServicer()

    server.connect_to_replicas(logfile="persistence_demo.log")

    assert len(server.accounts) == 4
    assert "alyssa" in server.accounts
    assert "dale" in server.accounts
    assert "aly1" in server.accounts
    assert "dale1" in server.accounts
    assert len(server.active_accounts) == 0
    assert len(server.public_events) == 1
    assert len(server.private_events) == 3

"""Testing new leader syncing backups in case of a power transition"""
def test_backup_sync():
    server = CalendarServicer(id="test_log_synced")
    server.connect_to_replicas(logfile="test_log_synced.log")

    # Setting up mocks
    lagging_server = CalendarServicer(id="test_log_sync_lag")
    lagging_server.connect_to_replicas(logfile="test_log_sync_lag.log")
    server.backup_connections = {lagging_server: "test_log_sync_lag"}
    lagging_server.process_line = MagicMock()

    # Server will be most up to date and will need to update a lagging backup server
    assert "aly1" in lagging_server.active_accounts
    assert "dale1" not in lagging_server.accounts
    assert len(lagging_server.private_events) == 2

    # Test backup sync
    server.sync_backups()
    
    assert lagging_server.process_line.call_count == 4
    args_list = lagging_server.process_line.call_args_list
    assert args_list[0][0][0] == "Logout successful.: aly1\n"
    assert args_list[1][0][0] == "Registration successful!: dale1\n"
    assert args_list[2][0][0] == "Private event scheduled.: dale1: 1682830800: 2: private: aly1\n"
    assert args_list[3][0][0] == "Logout successful.: dale1\n"


# Testing account-specific functions

"""Testing login flow"""
def test_login_flow():
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


"""Testing registration flow"""
def test_registration_flow():
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


"""Testing checking user exists flow"""
def test_check_user_exists_flow():
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


"""Testing account deletion flow"""
def test_delete_account_flow():
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
    server.public_events = [Event(host="dale")]
    server.private_events = [Event(host="dale", guestlist="bob"), Event(host="alyssa", guestlist="dale"), Event(host="alyssa", guestlist="dale, bob")]

    server.delete_account(request, None)

    assert len(server.accounts) == 0
    assert "dale" not in server.active_accounts
    assert "dale" not in server.new_event_notifications
    assert "dale" not in server.private_mappings

    # Tests 1) that all events with the account as host are removed, 2) that the account is removed from all guestlists,
    #       3) that if the account removal results in an event with no guests, that event is removed
    assert len(server.public_events) == 0
    assert len(server.private_events) == 1
    assert server.private_events[0].guestlist == "bob"

    proto.Text.assert_called_with(text=DELETION_SUCCESSFUL)


"""Testing logout flow"""
def test_logout_flow():
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.text = "dale"

    server.accounts.append("dale")
    server.active_accounts.append("dale")
    server.new_event_notifications["dale"] = ["new event"]
    server.private_mappings["dale"] = ["event_id"]

    server.logout(request, None)

    # Test that account is logged out but not deleted
    assert "dale" in server.accounts
    assert "dale" in server.new_event_notifications
    assert "dale" in server.private_mappings
    assert "dale" not in server.active_accounts

    proto.Text.assert_called_with(text=LOGOUT_SUCCESSFUL)


# Testing event-specific functions

"""Testing time conflicts in events"""
def test_check_conflict():
    server = CalendarServicer()

    # Setting up mocks
    event1 = Event(starttime=1682830800, duration=1)
    event2 = Event(starttime=1682830800, duration=1)
    assert server.check_conflict(event1, event2)


"""Testing public event creation flow"""
def test_schedule_public_event():
    server = CalendarServicer()

    # Setting up mocks
    server.check_conflict = MagicMock(return_value=False)
    server.accounts = ["alyssa", "maegan"]
    proto.Text=MagicMock()
    request = MagicMock()
    request.host = "alyssa"
    request.starttime = 1
    request.duration = 1
    request.description = "description"
    server.new_event_notifications["maegan"] = []
    server.public_events = [3, 4]
    server.private_events = [1, 2]

    # Test creating a public event
    server.schedule_public_event(request, None)

    # Check that a notification was sent to all users
    assert len(server.new_event_notifications["maegan"]) == 1
    # Checks that time conflict is checked for all events (public and private)
    assert server.check_conflict.call_count == 4
    assert len(server.public_events) == 3

    proto.Text.assert_called_with(text=PUBLIC_EVENT_SCHEDULED)


"""Testing private event creation flow"""""
def test_schedule_private_event():
    server = CalendarServicer()

    # Setting up mocks
    server.check_conflict = MagicMock(return_value=False)
    proto.Text=MagicMock()
    request = MagicMock()
    request.host = "alyssa"
    request.starttime = 1
    request.duration = 1
    request.description = "description"
    request.guestlist = "maegan"

    server.private_mappings["alyssa"] = []
    server.private_mappings["maegan"] = [1]
    server.public_events = [3, 4]
    server.private_events = [Event(id=1), Event(id=2)]
    server.new_event_notifications["maegan"] = []

    # Test creating a private event
    server.schedule_private_event(request, None)

    # Check that a notification was sent to invited guests
    assert len(server.new_event_notifications["maegan"]) == 1
    # Checks that time conflict is checked for all public events and guest's private events
    assert server.check_conflict.call_count == 3
    assert len(server.private_events) == 3

    proto.Text.assert_called_with(text=PRIVATE_EVENT_SCHEDULED)


"""Testing public event editing flow"""
def test_edit_public_event():
    server = CalendarServicer()

    # Setting up mocks
    server.check_conflict = MagicMock(return_value=False)
    proto.Text=MagicMock()
    request = MagicMock()
    request.id = 3
    request.starttime = 1
    request.duration = 1
    request.description = "description"

    server.public_events = [Event(id=3), Event(id=4)]
    server.private_events = [Event(id=1), Event(id=2)]

    # Test editing a public event
    server.edit_event(request, None)

    # Ensures that time conflicts are checked for all public events
    assert server.check_conflict.call_count == 2
    assert len(server.public_events) == 2
    assert server.public_events[0].duration == 1

    proto.Text.assert_called_with(text=UPDATE_SUCCESSFUL)


"""Testing private event editing flow"""
def test_edit_private_event():
    server = CalendarServicer()

    # Setting up mocks
    server.check_conflict = MagicMock(return_value=False)
    proto.Text=MagicMock()
    request = MagicMock()
    request.id = 2
    request.starttime = 1
    request.duration = 1
    request.description = "description"

    server.public_events = [Event(id=3), Event(id=4)]
    server.private_events = [Event(id=1), Event(id=2)]

    # Test editing a private event
    server.edit_event(request, None)

    # Ensures that time conflicts are checked for all public events and private events
    assert server.check_conflict.call_count == 2
    assert len(server.private_events) == 2
    assert server.private_events[1].duration == 1

    proto.Text.assert_called_with(text=UPDATE_SUCCESSFUL)


"""Testing event deletion flow"""
def test_delete_event():
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()
    request.id = 3
    server.public_events = [Event(id=3), Event(id=4)]
    server.private_events = [Event(id=1), Event(id=2, host="alyssa", guestlist="maegan")]
    server.private_mappings["maegan"] = [2]
    server.private_mappings["alyssa"] = [2]

    # Test deleting a public event
    server.delete_event(request, None)

    assert len(server.public_events) == 1
    assert server.public_events[0].id == 4
    assert len(server.private_events) == 2

    proto.Text.assert_called_with(text=EVENT_DELETED)

    # Test deleting a private event
    request.id = 2

    server.delete_event(request, None)

    assert len(server.private_events) == 1
    assert server.private_events[0].id == 1
    assert len(server.public_events) == 1
    assert len(server.private_mappings["maegan"]) == 0
    assert len(server.private_mappings["alyssa"]) == 0

    proto.Text.assert_called_with(text=EVENT_DELETED)


"""Testing event search flow for all events"""
def test_search_all_events():
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()

    server.public_events = [Event(id=1, host="alyssa", starttime=1, duration=1, description="public event 1", guestlist="maegan"),
                            Event(id=2, host="maegan", starttime=1, duration=1, description="public event 2", guestlist="alyssa")]
    server.private_events = [Event(id=3, host="alyssa", starttime=1, duration=1, description="private event 1", guestlist="maegan"), 
                             Event(id=4, host="maegan", starttime=1, duration=1, description="private event 2", guestlist="alyssa")]

    # Test searching all events
    request.function = SEARCH_ALL_EVENTS
    results = server.search_events(request, None)

    count = 0
    for result in results:
        count += 1
    
    assert count == 4


"""Testing searching for events by user (host)"""
def test_search_user_events():
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()

    server.public_events = [Event(id=1, host="alyssa", starttime=1, duration=1, description="public event 1", guestlist="maegan"),
                            Event(id=2, host="maegan", starttime=1, duration=1, description="public event 2", guestlist="alyssa")]
    server.private_events = [Event(id=3, host="alyssa", starttime=1, duration=1, description="private event 1", guestlist="maegan"), 
                             Event(id=4, host="maegan", starttime=1, duration=1, description="private event 2", guestlist="alyssa")]

    # Test searching events by user
    request.function = SEARCH_USER
    request.value = "alyssa"
    results = server.search_events(request, None)

    count = 0
    for result in results:
        assert result.host == "alyssa"
        count += 1
    
    assert count == 2

    # Testing that an appropriate message is returned when there is no match
    request.function = SEARCH_USER
    request.value = "bob"
    results = server.search_events(request, None)

    count = 0
    for result in results:
        assert result.returntext == NO_MATCH
        count += 1
    
    assert count == 1


"""Testing searching for events by description"""""
def test_search_description_events():
    server = CalendarServicer()

    # Setting up mocks
    proto.Text=MagicMock()
    request = MagicMock()

    server.public_events = [Event(id=1, host="alyssa", starttime=1, duration=1, description="public event 1", guestlist="maegan"),
                            Event(id=2, host="maegan", starttime=1, duration=1, description="public event 2", guestlist="alyssa")]
    server.private_events = [Event(id=3, host="alyssa", starttime=1, duration=1, description="private event 1", guestlist="maegan"), 
                             Event(id=4, host="maegan", starttime=1, duration=1, description="private event 2", guestlist="alyssa")]

    # Test searching all events
    request.function = SEARCH_DESCRIPTION
    request.value = "public event 1"
    results = server.search_events(request, None)

    count = 0
    for result in results:
        assert result.description == "public event 1"
        count += 1
    
    assert count == 1

    # Testing that an appropriate message is returned when there is no match
    request.function = SEARCH_DESCRIPTION
    request.value = "bad description"
    results = server.search_events(request, None)

    count = 0
    for result in results:
        assert result.returntext == NO_MATCH
        count += 1
    
    assert count == 1
