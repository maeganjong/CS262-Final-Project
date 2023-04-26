# CS262-Final-Project

python3 -m grpc_tools.protoc -I./protos --python_out=. --pyi_out=. --grpc_python_out=. ./protos/new_route_guide.proto

python3 run_calendar_server1.py
python3 run_calendar_client.py