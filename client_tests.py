from client import CalendarClient
from commands import *
from unittest.mock import MagicMock
from unittest.mock import patch
from io import StringIO

# pytest client_tests.py

# Testing account-specific functions

"""Testing registration flow"""
def test_registration_flow():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.logged_in = False
    client.username = None
    client.connection = MagicMock()
    client.connection.register_user = MagicMock(return_value=MagicMock(text=LOGIN_SUCCESSFUL))

    # Test registration
    with patch("builtins.input", side_effect=["0", "dale"]):
        assert not client.logged_in
        assert not client.username

        client.login()

        client.connection.register_user.assert_called_once()
        call_arg = client.connection.register_user.call_args.args[0]
        assert call_arg.text == "dale"
        assert client.logged_in
        assert client.username == "dale"


"""Testing login flow"""
def test_login_flow():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.logged_in = False
    client.username = None
    client.connection = MagicMock()
    client.connection.login_user = MagicMock(return_value=MagicMock(text=LOGIN_SUCCESSFUL))

    # Test registration
    with patch("builtins.input", side_effect=["1", "dale"]):
        assert not client.logged_in
        assert not client.username

        client.login()

        client.connection.login_user.assert_called_once()
        call_arg = client.connection.login_user.call_args.args[0]
        assert call_arg.text == "dale"
        assert client.logged_in
        assert client.username == "dale"


"""Testing display accounts"""
def test_display_accounts():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.connection = MagicMock()
    client.connection.display_accounts = MagicMock(return_value=[MagicMock(text="dale"), MagicMock(text="dallen")])

    # Test registration
    with patch("builtins.input", side_effect=["dale"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.display_accounts()
            client.connection.display_accounts.assert_called_once()
            call_arg = client.connection.display_accounts.call_args.args[0]
            assert call_arg.text == "dale"

            assert terminal_output.getvalue() == "\nUsers:\ndale\ndallen\n"


"""Testing delete account"""
def test_delete_account():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.logged_in = True
    client.username = "dale"
    client.connection = MagicMock()
    client.connection.delete_account = MagicMock(return_value=MagicMock(text=DELETION_SUCCESSFUL))
    client.login = MagicMock(return_value=None)

    # Test delete account
    assert client.logged_in
    assert client.username

    client.delete_account()

    client.connection.delete_account.assert_called_once()
    call_arg = client.connection.delete_account.call_args.args[0]
    assert call_arg.text == "dale"
    assert not client.logged_in
    assert not client.username


"""Testing logout"""""
def test_logout():
    # Testing logout flow
    client = CalendarClient(test=True)

    # Setting up mocks
    client.logged_in = True
    client.username = "dale"
    client.connection = MagicMock()
    client.connection.logout = MagicMock(return_value=MagicMock(text=LOGOUT_SUCCESSFUL))
    client.login = MagicMock(return_value=None)

    # Test logout
    assert client.logged_in
    assert client.username

    client.logout()

    client.connection.logout.assert_called_once()
    call_arg = client.connection.logout.call_args.args[0]
    assert call_arg.text == "dale"
    assert not client.logged_in
    assert not client.username


# Testing event-specific functions

"""Testing date prompting and error catching"""
def test_prompt_date():
    client = CalendarClient(test=True)

    # Test prompt date
    with patch("builtins.input", side_effect=["2023", "5", "2", "1"]):
        year, month, day, hour = client.prompt_date()

        assert year == 2023
        assert month == 5
        assert day == 2
        assert hour == 1
    
    # Test prompt date with invalid date
    with patch("builtins.input", side_effect=["-1", "2023", "13", "5", "-1", "2", "25", "1"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            year, month, day, hour = client.prompt_date()

            assert "Year not inputted correctly.\n" in terminal_output.getvalue()
            assert year == 2023
            assert "Month not inputted correctly.\n" in terminal_output.getvalue()
            assert month == 5
            assert "Date inputted incorrectly\n" in terminal_output.getvalue()
            assert day == 2
            assert "Hour inputted incorrectly\n" in terminal_output.getvalue()
            assert hour == 1


"""Test scheduling public event"""
def test_schedule_public_event():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.schedule_public_event = MagicMock(return_value=MagicMock(text="Event scheduled!"))

    # Test scheduling public event
    with patch("builtins.input", side_effect=["2023", "5", "2", "1", "3", "test event"]):
        client.schedule_event()

        client.connection.schedule_public_event.assert_called_once()
        test_event = client.connection.schedule_public_event.call_args.args[0]
        assert test_event.host == "alyssa"
        assert test_event.starttime == 1683003600
        assert test_event.duration == 3
        assert test_event.description == "test event"


"""Test scheduling private event"""""
def test_schedule_private_event():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.schedule_private_event = MagicMock(return_value=MagicMock(text="Event scheduled!"))
    client.connection.check_user_exists = MagicMock(return_value=MagicMock(text="User exists!"))

    # Test scheduling private event
    with patch("builtins.input", side_effect=["2023", "5", "2", "1", "3", "test event", "bob, dale"]):
        client.schedule_event(public=False)

        assert client.connection.check_user_exists.call_count == 2
        call_arg = client.connection.check_user_exists.call_args_list[0][0][0]
        assert call_arg.text == "bob"

        call_arg = client.connection.check_user_exists.call_args_list[1][0][0]
        assert call_arg.text == "dale"

        client.connection.schedule_private_event.assert_called_once()
        test_event = client.connection.schedule_private_event.call_args.args[0]
        assert test_event.host == "alyssa"
        assert test_event.starttime == 1683003600
        assert test_event.duration == 3
        assert test_event.description == "test event"
        assert test_event.guestlist == "bob, dale"


"""Testing editing event"""""
def test_edit_event():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.edit_event = MagicMock(return_value=MagicMock(text="Event edited!"))
    user_events = [MagicMock(id=1, duration=1, description="hi"), MagicMock(text=2, duration=1, description="bye")]
    client.connection.search_events = MagicMock(return_value=user_events)

    # Test editing private event successfully
    with patch("builtins.input", side_effect=["1", "d", "2"]):
        client.edit_event()

        client.connection.edit_event.assert_called_once()
        edited_event = client.connection.edit_event.call_args.args[0]
        assert edited_event.id == 1
        assert edited_event.duration == 2
        assert edited_event.description == "hi"


"""Testing editing/deleting event with invalid event id"""""
def test_event_invalid_id():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.edit_event = MagicMock(return_value=MagicMock(text="Event edited!"))
    client.connection.delete_event = MagicMock(return_value=MagicMock(text="Event deleted!"))

    # Testing invalid id for editing event
    with patch("builtins.input", side_effect=["x", "d", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.edit_event()
            client.connection.edit_event.assert_not_called()
            assert "\nInvalid event id.\n" in terminal_output.getvalue()
    
    # Testing invalid id for deleting event
    with patch("builtins.input", side_effect=["x", "d", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.delete_event()
            client.connection.delete_event.assert_not_called()
            assert "\nInvalid event id.\n" in terminal_output.getvalue()


"""Testing editing/deleting event with invalid permissions"""""
def test_event_permissions():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.edit_event = MagicMock(return_value=MagicMock(text="Event edited!"))
    client.connection.delete_event = MagicMock(return_value=MagicMock(text="Event deleted!"))
    user_events = [MagicMock(id=1, duration=1, description="hi"), MagicMock(text=2, duration=1, description="bye")]
    client.connection.search_events = MagicMock(return_value=user_events)

    # Testing editing event invalid permissions
    with patch("builtins.input", side_effect=["3", "d", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.edit_event()
            client.connection.edit_event.assert_not_called()
            assert "\nYou do not have permission to edit this event or this event does not exist.\n" in terminal_output.getvalue()
    
    # Testing deleting event invalid permissions
    with patch("builtins.input", side_effect=["3", "d", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.delete_event()
            client.connection.delete_event.assert_not_called()
            assert "\nYou do not have permission to delete this event.\n" in terminal_output.getvalue()


"""Testing editing event with invalid field formatting"""""
def test_edit_event_invalid_format():
    # Testing editing event
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.edit_event = MagicMock(return_value=MagicMock(text="Event edited!"))
    user_events = [MagicMock(id=1, duration=1, description="hi"), MagicMock(text=2, duration=1, description="bye")]
    client.connection.search_events = MagicMock(return_value=user_events)

    # Testing invalid id
    with patch("builtins.input", side_effect=["1", "", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.edit_event()
            client.connection.edit_event.assert_not_called()
            assert "\nNo fields to edit.\n" in terminal_output.getvalue()
    
    with patch("builtins.input", side_effect=["1", "a, b, c", "2"]):
        with patch('sys.stdout', new = StringIO()) as terminal_output:
            client.edit_event()
            client.connection.edit_event.assert_not_called()
            assert "\nNot inputted correctly!\n" in terminal_output.getvalue()


"""Testing deleting event"""""
def test_delete_event():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.delete_event = MagicMock(return_value=MagicMock(text="Event deleted!"))
    user_events = [MagicMock(id=1), MagicMock(text=2)]
    client.connection.search_events = MagicMock(return_value=user_events)

    # Test deleting event
    with patch("builtins.input", side_effect=["1"]):
        client.delete_event()

        client.connection.delete_event.assert_called_once()
        edited_event = client.connection.delete_event.call_args.args[0]
        assert edited_event.id == 1


"""Testing searching events"""""
def test_search_events():
    client = CalendarClient(test=True)

    # Setting up mocks
    client.username = "alyssa"
    client.connection = MagicMock()
    client.connection.search_events = MagicMock()

    # Test searching all events
    client.search_events(display_all=True)
    client.connection.search_events.assert_called_once()
    args = client.connection.search_events.call_args.args[0]
    assert args.function == SEARCH_ALL_EVENTS

    # Test searching events by user
    with patch("builtins.input", side_effect=["alyssa"]):
        client.search_events(option=SEARCH_USER)
        assert client.connection.search_events.call_count == 2
        args = client.connection.search_events.call_args.args[0]
        assert args.function == SEARCH_USER
        assert args.value == "alyssa"

    # Test searching events by description
    with patch("builtins.input", side_effect=["description"]):
        client.search_events(option=SEARCH_DESCRIPTION)
        assert client.connection.search_events.call_count == 3
        args = client.connection.search_events.call_args.args[0]
        assert args.function == SEARCH_DESCRIPTION
        assert args.value == "description"
