from client import CalendarClient
from commands import *
from unittest.mock import MagicMock
from unittest.mock import patch
from io import StringIO

# pytest client_tests.py

# Testing account-specific functions

def test_registration_flow():
    # Testing registration flow
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


def test_login_flow():
    # Testing login flow
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


def test_display_accounts():
    # Testing display accounts
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


def test_delete_flow():
    # Testing delete flow
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


def test_logout_flow():
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

def test_prompt_date():
    # TODO: FOR FINAL SUBMISSION
    pass


def test_schedule_public_event():
    # Testing send message
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


def test_schedule_private_event():
    # Testing send message
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


def test_edit_event():
    # TODO: FOR FINAL SUBMISSION
    pass


def test_delete_event():
    # TODO: FOR FINAL SUBMISSION
    pass


def test_search_events():
    # TODO: FOR FINAL SUBMISSION
    pass
