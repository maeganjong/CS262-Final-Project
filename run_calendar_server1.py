from server import *

replica_id, address = REPLICA_IDS[0]
calendar_server = ServerRunner(id=replica_id, address=address)
print("[STARTING] lead server is starting...")
calendar_server.start()

calendar_server.connect_to_replicas()

calendar_server.wait_for_termination()