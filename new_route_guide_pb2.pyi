from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Empty(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class Event(_message.Message):
    __slots__ = ["description", "endtime", "host", "invitee", "starttime"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ENDTIME_FIELD_NUMBER: _ClassVar[int]
    HOST_FIELD_NUMBER: _ClassVar[int]
    INVITEE_FIELD_NUMBER: _ClassVar[int]
    STARTTIME_FIELD_NUMBER: _ClassVar[int]
    description: str
    endtime: int
    host: str
    invitee: str
    starttime: int
    def __init__(self, host: _Optional[str] = ..., invitee: _Optional[str] = ..., description: _Optional[str] = ..., starttime: _Optional[int] = ..., endtime: _Optional[int] = ...) -> None: ...

class Text(_message.Message):
    __slots__ = ["text"]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...
