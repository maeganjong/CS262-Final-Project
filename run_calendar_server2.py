from server import *

replica_id, address = REPLICA_IDS[1]
calendar_server = ServerRunner(id=replica_id, address=address)
print("[STARTING] backup server is starting...")
calendar_server.start()

calendar_server.connect_to_replicas()

calendar_server.wait_for_termination()